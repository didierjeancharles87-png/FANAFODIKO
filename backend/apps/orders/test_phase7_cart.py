from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.marketplace.models import CatalogProduct, CatalogSeller
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country

from .models import Cart, CartItem

User = get_user_model()


class Phase7CartTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="patient")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="cart-admin", email="cart-admin@example.test", password="Valid-Cart-Password-934!"
        )
        self.seller = self.create_supplier("Vendeur panier", "REF-CART", verified=True)
        self.patient, self.account = self.create_patient("cart-patient")
        self.client = self.client_for(self.patient)
        self.product = self.create_equipment(self.seller, "Matériel panier", Decimal("12500.00"), stock=8)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_patient(self, username):
        user = User.objects.create_user(username=username, email=f"{username}@example.test", password="Valid-Cart-Password-934!")
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

    def create_equipment(self, seller, title, price, stock=5, status=CatalogProduct.Status.PUBLISHED):
        return CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title=title,
            seller=seller,
            price_mga=price,
            availability=CatalogProduct.Availability.AVAILABLE,
            status=status,
            moderation_status=CatalogProduct.ModerationStatus.APPROVED,
            submitted_for_review_at=timezone.now(),
            reviewed_by=self.admin,
            reviewed_at=timezone.now(),
            stock_quantity=stock,
            stock_updated_at=timezone.now() if stock is not None else None,
            equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
        )

    def add(self, product=None, quantity=1, **extra):
        payload = {"product": (product or self.product).pk, "quantity": quantity, **extra}
        return self.client.post("/api/v1/cart/", payload, format="json")

    def test_cart_totals_are_recomputed_from_database_price(self):
        response = self.add(quantity=2, price_mga="1.00", unit_price_mga="1.00")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["item_count"], 1)
        self.assertEqual(data["total_mga"], "25000.00")
        self.assertEqual(data["items"][0]["unit_price_mga"], "12500.00")
        self.assertEqual(data["items"][0]["line_total_mga"], "25000.00")
        self.assertTrue(AuditEvent.objects.filter(action="cart.item.added", actor=self.patient).exists())

        self.product.price_mga = Decimal("13000.00")
        self.product.save(update_fields=("price_mga", "price_updated_at", "updated_at"))
        refreshed = self.client.get("/api/v1/cart/")
        self.assertEqual(refreshed.status_code, 200, refreshed.content)
        self.assertEqual(refreshed.json()["total_mga"], "26000.00")

    def test_quantity_bounds_are_enforced(self):
        for quantity in (0, 100, -1):
            response = self.add(quantity=quantity)
            self.assertEqual(response.status_code, 400, (quantity, response.content))
        self.assertEqual(CartItem.objects.count(), 0)

        oversized = self.add(quantity=9)
        self.assertEqual(oversized.status_code, 400, oversized.content)
        self.assertIn("quantity", oversized.json()["error"]["details"])

    def test_non_orderable_products_are_rejected(self):
        draft = self.create_equipment(self.seller, "Brouillon", Decimal("1000.00"), stock=2, status=CatalogProduct.Status.DRAFT)
        no_stock = self.create_equipment(self.seller, "Sans stock", Decimal("1000.00"), stock=None)
        zero_stock = self.create_equipment(self.seller, "Rupture", Decimal("1000.00"), stock=0)
        unverified_seller = self.create_supplier("Vendeur non vérifié", "REF-CART-NO", verified=False)
        unverified_product = self.create_equipment(unverified_seller, "Produit vendeur non vérifié", Decimal("1000.00"), stock=2)

        for product in (draft, no_stock, zero_stock, unverified_product):
            response = self.add(product=product)
            self.assertEqual(response.status_code, 400, (product.title, response.content))
            self.assertIn("product", response.json()["error"]["details"])
        self.assertEqual(CartItem.objects.count(), 0)

    def test_medicine_requires_verified_amm(self):
        user, _, pharmacy = self.create_pharmacy("cart-pharmacy")
        del user
        product = CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.MEDICINE,
            title="Médicament sans AMM",
            seller=pharmacy,
            price_mga=Decimal("2000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            status=CatalogProduct.Status.PUBLISHED,
            moderation_status=CatalogProduct.ModerationStatus.APPROVED,
            submitted_for_review_at=timezone.now(),
            reviewed_by=self.admin,
            reviewed_at=timezone.now(),
            stock_quantity=3,
            stock_updated_at=timezone.now(),
            active_ingredient="Paracétamol",
            dosage="500 mg",
            pharmaceutical_form="Comprimé",
            packaging="Boîte",
            requires_prescription=True,
            authorization_status=CatalogProduct.AuthorizationStatus.PENDING,
        )
        response = self.add(product=product)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("product", response.json()["error"]["details"])

    def create_pharmacy(self, username):
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
        return user, account, seller

    def test_patient_only_accesses_own_cart_items(self):
        first = self.add(quantity=2)
        self.assertEqual(first.status_code, 201, first.content)
        item_id = first.json()["items"][0]["id"]

        other_user, other_account = self.create_patient("cart-patient-b")
        other_client = self.client_for(other_user)
        self.assertEqual(other_client.get("/api/v1/cart/").json()["items"], [])

        forbidden_patch = other_client.patch(f"/api/v1/cart/items/{item_id}/", {"quantity": 9}, format="json")
        self.assertEqual(forbidden_patch.status_code, 404, forbidden_patch.content)
        forbidden_delete = other_client.delete(f"/api/v1/cart/items/{item_id}/")
        self.assertEqual(forbidden_delete.status_code, 404, forbidden_delete.content)
        self.assertTrue(CartItem.objects.filter(pk=item_id).exists())
        del other_account

    def test_update_and_remove_cart_items(self):
        self.assertEqual(self.add(quantity=2).status_code, 201)
        item = CartItem.objects.get()
        updated = self.client.patch(f"/api/v1/cart/items/{item.pk}/", {"quantity": 4}, format="json")
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["items"][0]["quantity"], 4)
        self.assertEqual(updated.json()["total_mga"], "50000.00")
        self.assertTrue(AuditEvent.objects.filter(action="cart.item.updated", actor=self.patient).exists())

        removed = self.client.delete(f"/api/v1/cart/items/{item.pk}/")
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertEqual(removed.json()["items"], [])
        self.assertEqual(removed.json()["total_mga"], "0.00")
        self.assertFalse(CartItem.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(action="cart.item.removed", actor=self.patient).exists())

    def test_non_patient_cannot_use_cart(self):
        user = User.objects.create_user(username="cart-partner", email="cart-partner@example.test", password="Valid-Cart-Password-934!")
        client = self.client_for(user)
        self.assertEqual(client.get("/api/v1/cart/").status_code, 403)
        denied = client.post("/api/v1/cart/", {"product": self.product.pk, "quantity": 1}, format="json")
        self.assertEqual(denied.status_code, 403, denied.content)
