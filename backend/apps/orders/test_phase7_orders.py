from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.marketplace.models import CatalogProduct, CatalogSeller, SellerOwner
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country

from .models import Cart, CartItem, Order, OrderStatus
from .services import add_cart_item, transition_order

User = get_user_model()


class Phase7OrderTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="patient")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="orders-admin", email="orders-admin@example.test", password="Valid-Order-Password-934!"
        )
        self.seller = self.create_supplier("Vendeur commandes", "REF-ORDER", verified=True)
        self.patient, self.account = self.create_patient("orders-patient")
        self.client = self.client_for(self.patient)
        self.partner_user, self.partner_account = self.create_patient("orders-partner")
        self.partner_user.groups.remove(Group.objects.get(name="patient"))
        SellerOwner.objects.create(account=self.partner_account, seller=self.seller)
        self.partner_client = self.client_for(self.partner_user)
        self.product = self.create_equipment(self.seller, "Matériel commande", Decimal("15000.00"), 6)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_patient(self, username):
        user = User.objects.create_user(username=username, email=f"{username}@example.test", password="Valid-Order-Password-934!")
        user.groups.add(Group.objects.get(name="patient"))
        account, _ = AccountProfile.objects.get_or_create(user=user)
        return user, account

    def create_supplier(self, name, reference, verified=True):
        return CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name=name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED if verified else CatalogSeller.VerificationStatus.PENDING,
            verification_reference=reference if verified else "",
        )

    def create_equipment(self, seller, title, price, stock):
        return CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title=title,
            seller=seller,
            price_mga=price,
            availability=CatalogProduct.Availability.AVAILABLE,
            status=CatalogProduct.Status.PUBLISHED,
            moderation_status=CatalogProduct.ModerationStatus.APPROVED,
            submitted_for_review_at=timezone.now(),
            reviewed_by=self.admin,
            reviewed_at=timezone.now(),
            stock_quantity=stock,
            stock_updated_at=timezone.now(),
            equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
        )

    def create_pharmacy_partner(self, username):
        user, account = self.create_patient(username)
        user.groups.remove(Group.objects.get(name="patient"))
        profile = ProfessionalProfile.objects.create(
            account=account,
            category=ProfessionalCategory.PHARMACY,
            legal_name=f"Pharmacie {username}",
            country=self.country,
            city="Antananarivo",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
        )
        user.groups.add(Group.objects.get(name="professional_verified"))
        seller = CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.PHARMACY,
            professional_profile=profile,
            name=profile.legal_name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
        )
        SellerOwner.objects.create(account=account, seller=seller)
        return user, account, seller

    def create_medicine(self, seller, title, stock):
        return CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.MEDICINE,
            title=title,
            seller=seller,
            price_mga=Decimal("4000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            status=CatalogProduct.Status.PUBLISHED,
            moderation_status=CatalogProduct.ModerationStatus.APPROVED,
            submitted_for_review_at=timezone.now(),
            reviewed_by=self.admin,
            reviewed_at=timezone.now(),
            stock_quantity=stock,
            stock_updated_at=timezone.now(),
            active_ingredient="Paracétamol",
            dosage="500 mg",
            pharmaceutical_form="Comprimé",
            packaging="Boîte",
            requires_prescription=True,
            authorization_status=CatalogProduct.AuthorizationStatus.VERIFIED,
            authorization_reference="AMM-ORDER-001",
            authorization_submitted_at=timezone.now(),
            authorization_verified_reference="AMM-ORDER-001",
            authorization_reviewed_by=self.admin,
            authorization_reviewed_at=timezone.now(),
            authorization_decision_tracked=True,
        )

    def add_to_cart(self, product, quantity):
        return add_cart_item(account=self.account, product_id=product.pk, quantity=quantity)

    def checkout(self, client=None, **payload):
        return (client or self.client).post("/api/v1/orders/", payload, format="json")

    def test_checkout_creates_snapshot_decrements_stock_and_clears_cart(self):
        self.add_to_cart(self.product, 2)
        response = self.checkout(customer_note="Retrait en pharmacie")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()[0]
        self.assertEqual(data["status"], "awaiting_seller")
        self.assertEqual(data["total_mga"], "30000.00")
        self.assertEqual(data["customer_note"], "Retrait en pharmacie")
        self.assertNotIn("payment_status", data)

        item = data["items"][0]
        self.assertEqual(item["title"], self.product.title)
        self.assertEqual(item["unit_price_mga"], "15000.00")
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["line_total_mga"], "30000.00")
        self.assertEqual(data["events"][0]["to_status"], "awaiting_seller")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)
        self.assertEqual(CartItem.objects.count(), 0)
        self.assertTrue(AuditEvent.objects.filter(action="orders.order.created", actor=self.patient).exists())

    def test_checkout_re_reads_database_price(self):
        self.add_to_cart(self.product, 1)
        self.product.price_mga = Decimal("17000.00")
        self.product.save(update_fields=("price_mga", "price_updated_at", "updated_at"))
        response = self.checkout()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()[0]["total_mga"], "17000.00")
        self.assertEqual(response.json()[0]["items"][0]["unit_price_mga"], "17000.00")

    def test_last_stock_cannot_be_reserved_twice(self):
        self.product.stock_quantity = 1
        self.product.save(update_fields=("stock_quantity", "stock_updated_at", "updated_at"))
        self.add_to_cart(self.product, 1)
        first = self.checkout()
        self.assertEqual(first.status_code, 201, first.content)

        cart = Cart.objects.get(account=self.account)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        second = self.checkout()
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn("product", second.json()["error"]["details"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)
        self.assertEqual(Order.objects.count(), 1)

        with self.assertRaises(DjangoValidationError):
            add_cart_item(account=self.account, product_id=self.product.pk, quantity=1)

    def test_empty_cart_is_rejected(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("cart", response.json()["error"]["details"])

    def test_client_and_partner_isolation(self):
        self.add_to_cart(self.product, 1)
        order_id = self.checkout().json()[0]["id"]

        other_user, _ = self.create_patient("orders-other-patient")
        other_client = self.client_for(other_user)
        self.assertEqual(other_client.get(f"/api/v1/orders/{order_id}/").status_code, 404)
        self.assertEqual(other_client.get("/api/v1/orders/").json(), [])

        other_seller = self.create_supplier("Autre vendeur commandes", "REF-ORDER-B", verified=True)
        other_user_b, other_account_b = self.create_patient("orders-other-partner")
        other_user_b.groups.remove(Group.objects.get(name="patient"))
        SellerOwner.objects.create(account=other_account_b, seller=other_seller)
        other_partner_client = self.client_for(other_user_b)

        self.assertEqual(other_partner_client.get(f"/api/v1/partner/orders/{order_id}/").status_code, 404)
        self.assertEqual(
            other_partner_client.post(f"/api/v1/partner/orders/{order_id}/accept/", {}, format="json").status_code,
            404,
        )
        self.assertEqual(self.client.post(f"/api/v1/partner/orders/{order_id}/accept/", {}, format="json").status_code, 403)

    def test_allowed_transition_chain_and_events(self):
        self.add_to_cart(self.product, 1)
        order_id = self.checkout().json()[0]["id"]

        accepted = self.partner_client.post(f"/api/v1/partner/orders/{order_id}/accept/", {}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertIsNotNone(accepted.json()["accepted_at"])

        forbidden = self.partner_client.post(f"/api/v1/partner/orders/{order_id}/mark-ready/", {}, format="json")
        self.assertEqual(forbidden.status_code, 400, forbidden.content)

        for path, expected in (
            ("prepare/", "preparing"),
            ("mark-ready/", "ready"),
            ("complete/", "completed"),
        ):
            response = self.partner_client.post(f"/api/v1/partner/orders/{order_id}/{path}", {}, format="json")
            self.assertEqual(response.status_code, 200, (path, response.content))
            self.assertEqual(response.json()["status"], expected)

        order = Order.objects.get(pk=order_id)
        self.assertEqual(
            list(order.events.values_list("to_status", flat=True)),
            ["awaiting_seller", "accepted", "preparing", "ready", "completed"],
        )
        self.assertTrue(AuditEvent.objects.filter(action="orders.order.status_changed", actor=self.partner_user).exists())

    def test_reject_requires_reason_and_uses_rejection_reason(self):
        self.add_to_cart(self.product, 1)
        order_id = self.checkout().json()[0]["id"]

        missing = self.partner_client.post(f"/api/v1/partner/orders/{order_id}/reject/", {}, format="json")
        self.assertEqual(missing.status_code, 400, missing.content)

        rejected = self.partner_client.post(
            f"/api/v1/partner/orders/{order_id}/reject/", {"reason": "Stock non conforme"}, format="json"
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        self.assertEqual(rejected.json()["status"], "rejected")
        self.assertEqual(rejected.json()["rejection_reason"], "Stock non conforme")

    def test_medicine_cannot_be_completed_without_pharmacist_prescription_check(self):
        pharmacy_user, _, pharmacy_seller = self.create_pharmacy_partner("orders-pharmacy")
        pharmacy_client = self.client_for(pharmacy_user)
        medicine = self.create_medicine(pharmacy_seller, "Médicament ordonnance", 4)

        self.add_to_cart(medicine, 1)
        order_id = self.checkout().json()[0]["id"]
        order = Order.objects.get(pk=order_id)
        item = order.items.get()
        self.assertTrue(item.requires_prescription)
        self.assertEqual(item.authorization_status, "verified")
        self.assertEqual(item.authorization_reference, "AMM-ORDER-001")

        self.assertEqual(
            pharmacy_client.post(f"/api/v1/partner/orders/{order_id}/accept/", {}, format="json").status_code,
            200,
        )
        pharmacy_client.post(f"/api/v1/partner/orders/{order_id}/prepare/", {}, format="json")
        pharmacy_client.post(f"/api/v1/partner/orders/{order_id}/mark-ready/", {}, format="json")
        blocked = pharmacy_client.post(f"/api/v1/partner/orders/{order_id}/complete/", {}, format="json")
        self.assertEqual(blocked.status_code, 400, blocked.content)

        self.add_to_cart(medicine, 1)
        checked_order_id = self.checkout().json()[0]["id"]
        accepted = pharmacy_client.post(
            f"/api/v1/partner/orders/{checked_order_id}/accept/",
            {"prescription_checked": True, "note": "Ordonnance vérifiée"},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        checked_order = Order.objects.get(pk=checked_order_id)
        self.assertTrue(checked_order.items.get().prescription_checked_by_seller)
        self.assertIsNotNone(checked_order.items.get().prescription_checked_at)
        pharmacy_client.post(f"/api/v1/partner/orders/{checked_order_id}/prepare/", {}, format="json")
        pharmacy_client.post(f"/api/v1/partner/orders/{checked_order_id}/mark-ready/", {}, format="json")
        completed = pharmacy_client.post(f"/api/v1/partner/orders/{checked_order_id}/complete/", {}, format="json")
        self.assertEqual(completed.status_code, 200, completed.content)

    def test_multi_seller_cart_creates_one_order_per_seller(self):
        second_seller = self.create_supplier("Deuxième vendeur", "REF-ORDER-C", verified=True)
        second_product = self.create_equipment(second_seller, "Autre matériel", Decimal("5000.00"), 3)
        self.add_to_cart(self.product, 1)
        self.add_to_cart(second_product, 2)

        response = self.checkout()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(response.json()), 2)
        totals = sorted(order["total_mga"] for order in response.json())
        self.assertEqual(totals, ["10000.00", "15000.00"])
        self.assertEqual(Order.objects.count(), 2)

    def test_service_rejects_invalid_transition_directly(self):
        self.add_to_cart(self.product, 1)
        order = self.checkout().json()[0]
        with self.assertRaises(DjangoValidationError):
            transition_order(
                Order.objects.get(pk=order["id"]),
                to_status=OrderStatus.COMPLETED,
                actor=self.partner_user,
            )
