from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile, BuyerAddress
from apps.marketplace.models import CatalogProduct, CatalogSeller, SellerOwner
from apps.reference.models import Country

from .models import DiscountType, Promotion, PromotionStatus
from .services import derive_promotion_prices


User = get_user_model()


class PromotionFlowTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="patient")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="promo-admin",
            email="promo-admin@example.test",
            password="Valid-Promo-Password-934!",
        )
        self.seller = self.create_supplier("Fournisseur promo", "REF-PROMO-1")
        self.patient, self.patient_account = self.create_patient("promo-patient")
        self.client = self.client_for(self.patient)
        self.partner_user, self.partner_account = self.create_patient("promo-partner")
        self.partner_user.groups.remove(Group.objects.get(name="patient"))
        SellerOwner.objects.create(account=self.partner_account, seller=self.seller)
        self.partner_client = self.client_for(self.partner_user)
        self.other_patient, self.other_account = self.create_patient("promo-other-patient")
        self.other_client = self.client_for(self.other_patient)
        self.product = self.create_equipment(self.seller, "Appareil promu", Decimal("10000.00"), 10)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_patient(self, username):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Valid-Promo-Password-934!",
        )
        user.groups.add(Group.objects.get(name="patient"))
        return user, user.account_profile

    def create_supplier(self, name, reference):
        return CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name=name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
            verification_reference=reference,
        )

    def create_equipment(self, seller, title, price, stock, **overrides):
        values = {
            "product_type": CatalogProduct.ProductType.EQUIPMENT,
            "title": title,
            "slug": f"{title.lower().replace(' ', '-')}-{CatalogProduct.objects.count()}",
            "seller": seller,
            "price_mga": price,
            "availability": CatalogProduct.Availability.AVAILABLE,
            "status": CatalogProduct.Status.PUBLISHED,
            "moderation_status": CatalogProduct.ModerationStatus.APPROVED,
            "submitted_for_review_at": timezone.now(),
            "reviewed_by": self.admin,
            "reviewed_at": timezone.now(),
            "stock_quantity": stock,
            "stock_updated_at": timezone.now(),
            "equipment_category": CatalogProduct.EquipmentCategory.DIAGNOSTIC,
        }
        values.update(overrides)
        return CatalogProduct.objects.create(**values)

    def promotion_payload(self, product=None, code="FANAFODIKO10", percent="10.00", **overrides):
        product = product or self.product
        now = timezone.now()
        values = {
            "product": product.pk,
            "code": code,
            "title": "PROMO -10 %",
            "discount_type": "percent",
            "discount_value": percent,
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=2)).isoformat(),
        }
        values.update(overrides)
        return values

    def submit_promotion(self, product=None, code="FANAFODIKO10", **overrides):
        return self.partner_client.post(
            "/api/v1/promotions/partner/",
            self.promotion_payload(product=product, code=code, **overrides),
            format="json",
        )

    def make_active_promotion(self, product=None, code="FANAFODIKO10", **overrides):
        product = product or self.product
        now = timezone.now()
        values = self.promotion_payload(product=product, code=code)
        values.pop("title")
        values["product"] = product
        values["starts_at"] = now - timedelta(hours=1)
        values["ends_at"] = now + timedelta(days=2)
        original, promotional = derive_promotion_prices(
            original_price=product.price_mga,
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal(values["discount_value"]),
        )
        values["original_price_mga"] = original
        values["promotional_price_mga"] = promotional
        values.update({
            "seller": product.seller,
            "status": PromotionStatus.ACTIVE,
            "reviewed_by": self.admin,
            "reviewed_at": now,
            "created_by": self.partner_user,
        })
        values.update(overrides)
        return Promotion.objects.create(**values)

    def add_to_cart(self, product, quantity=1):
        return self.client.post(
            "/api/v1/cart/",
            {"product": product.pk, "quantity": quantity},
            format="json",
        )

    def test_partner_submits_pending_promotion_without_direct_publication(self):
        response = self.submit_promotion()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], PromotionStatus.PENDING)
        public = APIClient().get("/api/v1/promotions/public/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["count"], 0)
        activation = self.partner_client.post(f"/api/v1/promotions/partner/{response.json()['id']}/activate/", {}, format="json")
        self.assertEqual(activation.status_code, 400)
        self.assertEqual(Promotion.objects.get(code="FANAFODIKO10").status, PromotionStatus.PENDING)

    def test_partner_cannot_force_prices_in_promotion_payload(self):
        payload = self.promotion_payload()
        payload.update({"original_price_mga": "1.00", "promotional_price_mga": "0.50"})
        response = self.partner_client.post("/api/v1/promotions/partner/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        promotion = Promotion.objects.get(code="FANAFODIKO10")
        self.assertEqual(promotion.original_price_mga, self.product.price_mga)
        self.assertEqual(promotion.promotional_price_mga, Decimal("9000.00"))
        self.assertEqual(response.json()["discount_label"], "-10 %")

    def test_admin_approval_then_partner_activation_makes_promotion_public(self):
        submitted = self.submit_promotion()
        promotion_id = submitted.json()["id"]
        approval = self.client_for(self.admin).post(
            f"/api/v1/promotions/admin/{promotion_id}/approve/", {}, format="json"
        )
        self.assertEqual(approval.status_code, 200, approval.content)
        self.assertEqual(approval.json()["status"], PromotionStatus.APPROVED)
        activation = self.partner_client.post(f"/api/v1/promotions/partner/{promotion_id}/activate/", {}, format="json")
        self.assertEqual(activation.status_code, 200, activation.content)
        public = APIClient().get("/api/v1/promotions/public/").json()
        self.assertEqual(public["count"], 1)
        self.assertEqual(public["results"][0]["code"], "FANAFODIKO10")
        self.assertEqual(public["results"][0]["discount_label"], "-10 %")
        product = APIClient().get(f"/api/v1/marketplace/public/products/{self.product.slug}/").json()
        self.assertEqual(product["effective_price_mga"], "9000.00")
        self.assertEqual(product["promotion"]["code"], "FANAFODIKO10")

    def test_expired_promotion_and_invalid_coupon_are_refused(self):
        self.make_active_promotion(ends_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(self.add_to_cart(self.product).status_code, 201)
        expired = self.client.post("/api/v1/cart/coupon/", {"code": "FANAFODIKO10"}, format="json")
        self.assertEqual(expired.status_code, 400)
        self.assertIn("expirée", str(expired.json()))
        invalid = self.client.post("/api/v1/cart/coupon/", {"code": "INVALIDE"}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_coupon_price_is_server_calculated_and_quantity_limit_enforced(self):
        self.make_active_promotion(max_redemptions=2)
        self.assertEqual(self.add_to_cart(self.product, 2).status_code, 201)
        applied = self.client.post("/api/v1/cart/coupon/", {"code": "FANAFODIKO10"}, format="json")
        self.assertEqual(applied.status_code, 200, applied.content)
        self.assertEqual(applied.json()["subtotal_mga"], "20000.00")
        self.assertEqual(applied.json()["discount_mga"], "2000.00")
        self.assertEqual(applied.json()["total_mga"], "18000.00")
        checkout = self.client.post("/api/v1/orders/", {}, format="json")
        self.assertEqual(checkout.status_code, 201, checkout.content)
        order = checkout.json()[0]
        self.assertEqual(order["subtotal_mga"], "20000.00")
        self.assertEqual(order["discount_mga"], "2000.00")
        self.assertEqual(order["total_mga"], "18000.00")
        self.assertEqual(order["items"][0]["unit_price_mga"], "9000.00")
        self.assertEqual(self.add_to_cart(self.product, 1).status_code, 201)
        exhausted = self.client.post("/api/v1/cart/coupon/", {"code": "FANAFODIKO10"}, format="json")
        self.assertEqual(exhausted.status_code, 400)
        self.assertIn("épuisée", str(exhausted.json()))

    def test_coupon_requires_its_product_and_buyer_orders_are_isolated(self):
        self.make_active_promotion()
        other_product = self.create_equipment(self.seller, "Autre appareil", Decimal("5000.00"), 4)
        self.assertEqual(self.add_to_cart(other_product).status_code, 201)
        wrong = self.client.post("/api/v1/cart/coupon/", {"code": "FANAFODIKO10"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(self.add_to_cart(self.product).status_code, 201)
        checkout = self.client.post("/api/v1/orders/", {}, format="json")
        self.assertEqual(checkout.status_code, 201, checkout.content)
        order_id = checkout.json()[0]["id"]
        self.assertEqual(self.other_client.get(f"/api/v1/orders/{order_id}/").status_code, 404)
        self.assertEqual(self.other_client.get("/api/v1/orders/").json(), [])

    def test_partner_cannot_manage_another_seller_promotion_or_order(self):
        other_seller = self.create_supplier("Autre fournisseur", "REF-PROMO-2")
        other_product = self.create_equipment(other_seller, "Appareil externe", Decimal("7000.00"), 3)
        other_promotion = self.make_active_promotion(product=other_product, code="AUTRE10")
        response = self.partner_client.get(f"/api/v1/promotions/partner/{other_promotion.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.add_to_cart(other_product).status_code, 201)
        order_id = self.client.post("/api/v1/orders/", {}, format="json").json()[0]["id"]
        self.assertEqual(self.partner_client.get(f"/api/v1/partner/orders/{order_id}/").status_code, 404)
        rejected = self.partner_client.post(
            f"/api/v1/promotions/partner/{other_promotion.pk}/deactivate/", {}, format="json"
        )
        self.assertEqual(rejected.status_code, 404)

    def test_medicine_and_moderation_restrictions_remain_enforced(self):
        unverified_medicine = self.create_equipment(
            self.seller,
            "Médicament non vérifié",
            Decimal("2000.00"),
            2,
            product_type=CatalogProduct.ProductType.MEDICINE,
            active_ingredient="Paracétamol",
            dosage="500 mg",
            pharmaceutical_form="Comprimé",
            packaging="Boîte",
            authorization_status=CatalogProduct.AuthorizationStatus.PENDING,
            authorization_reference="",
            equipment_category="",
        )
        medicine_promotion = self.make_active_promotion(
            product=unverified_medicine,
            code="MEDIC10",
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=1),
        )
        activation = self.partner_client.post(
            f"/api/v1/promotions/partner/{medicine_promotion.pk}/activate/", {}, format="json"
        )
        self.assertEqual(activation.status_code, 400)
        codes = [row["code"] for row in APIClient().get("/api/v1/promotions/public/").json()["results"]]
        self.assertNotIn("MEDIC10", codes)
        pending_product = self.create_equipment(
            self.seller,
            "Produit en modération",
            Decimal("3000.00"),
            2,
            moderation_status=CatalogProduct.ModerationStatus.PENDING,
            submitted_for_review_at=timezone.now(),
            reviewed_by=None,
            reviewed_at=None,
        )
        self.assertEqual(
            APIClient().get(f"/api/v1/marketplace/public/products/{pending_product.slug}/").status_code,
            404,
        )

    def test_removal_request_hides_promotion_until_admin_archives_it(self):
        promotion = self.make_active_promotion()
        self.assertEqual(APIClient().get("/api/v1/promotions/public/").json()["count"], 1)
        requested = self.partner_client.post(
            f"/api/v1/promotions/partner/{promotion.pk}/request-removal/", {}, format="json"
        )
        self.assertEqual(requested.status_code, 200, requested.content)
        self.assertEqual(requested.json()["status"], PromotionStatus.REMOVAL_REQUESTED)
        self.assertEqual(APIClient().get("/api/v1/promotions/public/").json()["count"], 0)
        unauthorised = self.partner_client.post(
            f"/api/v1/promotions/admin/{promotion.pk}/archive/", {}, format="json"
        )
        self.assertEqual(unauthorised.status_code, 403)
        archived = self.client_for(self.admin).post(
            f"/api/v1/promotions/admin/{promotion.pk}/archive/", {}, format="json"
        )
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertEqual(archived.json()["status"], PromotionStatus.ARCHIVED)
        self.assertTrue(Promotion.objects.filter(pk=promotion.pk).exists())

    def test_admin_rejection_requires_a_reason_and_partner_can_resubmit(self):
        submitted = self.submit_promotion(code="REFUSE10")
        promotion_id = submitted.json()["id"]
        admin_client = self.client_for(self.admin)
        without_reason = admin_client.post(
            f"/api/v1/promotions/admin/{promotion_id}/reject/", {}, format="json"
        )
        self.assertEqual(without_reason.status_code, 400)
        rejected = admin_client.post(
            f"/api/v1/promotions/admin/{promotion_id}/reject/",
            {"reason": "Remise non conforme à la politique commerciale."},
            format="json",
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        self.assertEqual(rejected.json()["status"], PromotionStatus.REJECTED)
        self.assertTrue(rejected.json()["review_notes"])
        resubmitted = self.partner_client.patch(
            f"/api/v1/promotions/partner/{promotion_id}/",
            {"title": "Nouvelle proposition"},
            format="json",
        )
        self.assertEqual(resubmitted.status_code, 200, resubmitted.content)
        self.assertEqual(resubmitted.json()["status"], PromotionStatus.PENDING)
        self.assertEqual(resubmitted.json()["review_notes"], "")

    def test_buyer_addresses_are_private_and_checkout_snapshots_owned_address(self):
        payload = {
            "label": "Retrait principal",
            "recipient_name": "Soa Rakoto",
            "phone_number": "+261 34 99 888 77",
            "country": self.country.pk,
            "region": "Analamanga",
            "city": "Antananarivo",
            "neighbourhood": "Antsakaviro",
            "complement": "Près du laboratoire",
            "is_primary": True,
        }
        created = self.client.post("/api/v1/accounts/patient/addresses/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        address_id = created.json()["id"]
        self.assertEqual(self.other_client.get(f"/api/v1/accounts/patient/addresses/{address_id}/").status_code, 404)
        self.assertEqual(
            self.other_client.patch(f"/api/v1/accounts/patient/addresses/{address_id}/", {"city": "Paris"}, format="json").status_code,
            404,
        )
        self.assertEqual(
            self.other_client.post(
                "/api/v1/cart/", {"product": self.product.pk, "quantity": 1}, format="json"
            ).status_code,
            201,
        )
        self.assertEqual(
            self.other_client.post("/api/v1/orders/", {"delivery_address": address_id}, format="json").status_code,
            400,
        )
        self.assertEqual(self.add_to_cart(self.product).status_code, 201)
        order = self.client.post("/api/v1/orders/", {"delivery_address": address_id}, format="json")
        self.assertEqual(order.status_code, 201, order.content)
        self.assertEqual(order.json()[0]["delivery_recipient"], "Soa Rakoto")
        self.assertEqual(order.json()[0]["delivery_city"], "Antananarivo")
        self.assertTrue(BuyerAddress.objects.get(pk=address_id).is_primary)
