from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country
from .models import CatalogProduct, CatalogSeller


User = get_user_model()


class MarketplaceAPITests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        self.admin = User.objects.create_superuser(username="catalog-admin", email="catalog-admin@example.test", password="Valid-Admin-Password-934!", first_name="Catalogue")
        AccountProfile.objects.get_or_create(user=self.admin)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.public_client = APIClient()

    def create_verified_pharmacy(self):
        user = User.objects.create_user(username="pharmacy-account", email="pharmacy@example.test", password="Valid-Pharmacy-Password-934!")
        account, _ = AccountProfile.objects.get_or_create(user=user)
        Group.objects.get_or_create(name="professional_verified")
        user.groups.add(Group.objects.get(name="professional_verified"))
        profile = ProfessionalProfile.objects.create(
            account=account,
            category=ProfessionalCategory.PHARMACY,
            legal_name="Pharmacie de test",
            country=self.country,
            region="Analamanga",
            city="Antananarivo",
        )
        profile.verification_status = ProfessionalProfile.VerificationStatus.APPROVED
        profile.save(update_fields=("verification_status", "updated_at"))
        return profile

    def create_pharmacy_seller(self):
        profile = self.create_verified_pharmacy()
        response = self.admin_client.post("/api/v1/marketplace/admin/sellers/", {
            "kind": "pharmacy",
            "professional_profile": profile.pk,
            "name": profile.legal_name,
            "country": self.country.pk,
            "region": "Analamanga",
            "city": "Antananarivo",
            "verification_status": "verified",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def create_medicine(self, seller_id, status="draft"):
        response = self.admin_client.post("/api/v1/marketplace/admin/products/", {
            "product_type": "medicine",
            "title": "Produit médical de test",
            "brand": "Marque de test",
            "seller": seller_id,
            "price_mga": "12000.00",
            "availability": "available",
            "status": status,
            "active_ingredient": "Substance test",
            "dosage": "500 mg",
            "pharmaceutical_form": "Comprimé",
            "packaging": "Boîte de 10",
            "requires_prescription": True,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def create_verified_supplier(self):
        response = self.admin_client.post("/api/v1/marketplace/admin/sellers/", {
            "kind": "medical_supplier",
            "name": "Fournisseur médical de test",
            "country": self.country.pk,
            "region": "Analamanga",
            "city": "Antananarivo",
            "verification_status": "verified",
            "verification_reference": "REF-TEST-2026",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_public_catalog_starts_empty_and_never_exposes_drafts(self):
        self.assertEqual(self.public_client.get("/api/v1/marketplace/public/medicines/").status_code, 200)
        self.assertEqual(self.public_client.get("/api/v1/marketplace/public/equipment/").status_code, 200)
        search = self.public_client.get("/api/v1/marketplace/public/search/?q=test").json()
        self.assertEqual(search["products"], [])
        self.assertEqual(search["deferred_categories"], ["pharmacies", "doctors", "specialists", "laboratories"])

        seller = self.create_pharmacy_seller()
        draft = self.create_medicine(seller["id"])
        response = self.public_client.get("/api/v1/marketplace/public/medicines/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(self.public_client.get(f"/api/v1/marketplace/public/products/{draft['slug']}/").status_code, 404)

    def test_medicine_publication_requires_verified_pharmacy_and_amm(self):
        seller = self.create_pharmacy_seller()
        draft = self.create_medicine(seller["id"])
        cannot_publish = self.admin_client.patch(f"/api/v1/marketplace/admin/products/{draft['id']}/", {"status": "published"}, format="json")
        self.assertEqual(cannot_publish.status_code, 400)
        self.assertIn("authorization_status", cannot_publish.json()["error"]["details"])

        CatalogProduct.objects.filter(pk=draft["id"]).update(authorization_reference="AMM-TEST-123")
        verified = self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{draft['id']}/authorization/verify/", {}, format="json"
        )
        self.assertEqual(verified.status_code, 200, verified.content)
        published = self.admin_client.patch(
            f"/api/v1/marketplace/admin/products/{draft['id']}/", {"status": "published"}, format="json"
        )
        self.assertEqual(published.status_code, 200, published.content)
        self.assertEqual(published.json()["requires_prescription"], True)
        public = self.public_client.get("/api/v1/marketplace/public/medicines/")
        self.assertEqual(public.json()["count"], 1)
        self.assertEqual(public.json()["results"][0]["seller"]["verified"], True)
        self.assertNotIn("authorization_reference", public.json()["results"][0])

    def test_equipment_supplier_needs_verification_and_publication_uses_true_fields(self):
        pending = self.admin_client.post("/api/v1/marketplace/admin/sellers/", {
            "kind": "medical_supplier", "name": "Fournisseur de test", "country": self.country.pk,
            "city": "Antananarivo", "verification_status": "pending",
        }, format="json")
        self.assertEqual(pending.status_code, 201, pending.content)
        cannot_verify = self.admin_client.patch(f"/api/v1/marketplace/admin/sellers/{pending.json()['id']}/", {"verification_status": "verified"}, format="json")
        self.assertEqual(cannot_verify.status_code, 400)

        seller = self.create_verified_supplier()
        product = self.admin_client.post("/api/v1/marketplace/admin/products/", {
            "product_type": "equipment", "title": "Matériel médical de test", "seller": seller["id"],
            "price_mga": "80000.00", "availability": "limited", "equipment_category": "diagnostic",
            "model_name": "Modèle test", "technical_specifications": {"Alimentation": "USB", "Poids": "1 kg"},
            "warranty": "Garantie indiquée par le fournisseur de test", "status": "published",
        }, format="json")
        self.assertEqual(product.status_code, 201, product.content)
        public = self.public_client.get("/api/v1/marketplace/public/equipment/?city=Antananarivo&min_price=50000")
        self.assertEqual(public.json()["count"], 1)
        self.assertEqual(public.json()["results"][0]["equipment_category"], "diagnostic")
        self.assertEqual(public.json()["results"][0]["availability"], "limited")
        self.assertIn("price_updated_at", public.json()["results"][0])
        self.assertIn("availability_updated_at", public.json()["results"][0])

    def test_public_orderability_reflects_unknown_and_unavailable_stock(self):
        seller = self.create_verified_supplier()
        product = CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title="Matériel au stock inconnu",
            seller=CatalogSeller.objects.get(pk=seller["id"]),
            price_mga=Decimal("15000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            status=CatalogProduct.Status.PUBLISHED,
            equipment_category=CatalogProduct.EquipmentCategory.OTHER,
            stock_quantity=None,
        )
        detail = lambda: self.public_client.get(f"/api/v1/marketplace/public/products/{product.slug}/").json()
        public = detail()
        self.assertFalse(public["is_orderable"])
        self.assertEqual(public["orderability_reason"], "Le stock de ce produit n’est pas renseigné.")

        product.stock_quantity = 3
        product.save(update_fields=("stock_quantity", "updated_at"))
        public = detail()
        self.assertTrue(public["is_orderable"])
        self.assertIsNone(public["orderability_reason"])

        product.availability = CatalogProduct.Availability.UNAVAILABLE
        product.save(update_fields=("availability", "updated_at"))
        public = detail()
        self.assertFalse(public["is_orderable"])
        self.assertEqual(public["orderability_reason"], "Ce produit est indisponible.")

    def test_admin_options_expose_eligible_pharmacies_and_active_accounts(self):
        self.create_pharmacy_seller()
        response = self.admin_client.get("/api/v1/marketplace/admin/options/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(any(
            pharmacy["name"] == "Pharmacie de test" and pharmacy["eligible"]
            for pharmacy in body["pharmacies"]
        ))
        self.assertTrue(any(
            account["email"] == "catalog-admin@example.test" and account["professional_profile"] is None
            for account in body["accounts"]
        ))

    def test_public_filters_validate_price_range(self):
        response = self.public_client.get("/api/v1/marketplace/public/medicines/?min_price=500&max_price=100")
        self.assertEqual(response.status_code, 400)
        self.assertIn("max_price", response.json()["error"]["details"])

    def test_only_active_staff_can_manage_and_delete_archives_instead(self):
        denied = self.public_client.post("/api/v1/marketplace/admin/sellers/", {}, format="json")
        self.assertEqual(denied.status_code, 403)
        seller = self.create_verified_supplier()
        product = self.admin_client.post("/api/v1/marketplace/admin/products/", {
            "product_type": "equipment", "title": "À archiver", "seller": seller["id"], "price_mga": "100.00",
            "equipment_category": "other", "status": "published",
        }, format="json")
        self.assertEqual(product.status_code, 201, product.content)
        archived = self.admin_client.delete(f"/api/v1/marketplace/admin/products/{product.json()['id']}/")
        self.assertEqual(archived.status_code, 204)
        self.assertEqual(CatalogProduct.objects.get(pk=product.json()["id"]).status, CatalogProduct.Status.ARCHIVED)
        self.assertEqual(AuditEvent.objects.filter(action="marketplace.product.archived").count(), 1)

    def test_pharmacy_seller_cannot_link_to_another_professional_category(self):
        user = User.objects.create_user(username="doctor-account", email="doctor@example.test", password="Valid-Doctor-Password-934!")
        account, _ = AccountProfile.objects.get_or_create(user=user)
        profile = ProfessionalProfile.objects.create(account=account, category=ProfessionalCategory.DOCTOR, legal_name="Médecin de test")
        response = self.admin_client.post("/api/v1/marketplace/admin/sellers/", {
            "kind": "pharmacy", "professional_profile": profile.pk, "name": "Vendeur inadapté",
            "country": self.country.pk, "city": "Antananarivo",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("professional_profile", response.json()["error"]["details"])
