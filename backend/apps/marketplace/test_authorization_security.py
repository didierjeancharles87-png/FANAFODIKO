"""Tests E3 : déclaration partenaire, décision administrative et traçabilité AMM."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country

from .models import CatalogProduct, CatalogSeller, SellerOwner


User = get_user_model()


class AuthorizationWorkflowTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="amm-admin", email="amm-admin@example.test", password="Valid-Amm-Password-934!"
        )
        AccountProfile.objects.get_or_create(user=self.admin)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.public_client = APIClient()

        self.partner = User.objects.create_user(
            username="amm-partner", email="amm-partner@example.test", password="Valid-Amm-Password-934!"
        )
        account, _ = AccountProfile.objects.get_or_create(user=self.partner)
        profile = ProfessionalProfile.objects.create(
            account=account,
            category=ProfessionalCategory.PHARMACY,
            legal_name="Pharmacie AMM",
            country=self.country,
            city="Antananarivo",
            verification_status=ProfessionalProfile.VerificationStatus.APPROVED,
        )
        self.partner.groups.add(Group.objects.get(name="professional_verified"))
        self.seller = CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.PHARMACY,
            professional_profile=profile,
            name=profile.legal_name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
        )
        SellerOwner.objects.create(account=account, seller=self.seller)
        self.partner_client = APIClient()
        self.partner_client.force_authenticate(self.partner)

    def create_medicine(self, title, reference="", **extra):
        payload = {
            "product_type": "medicine",
            "title": title,
            "brand": "Laboratoire test",
            "description": "Fiche de test AMM",
            "price_mga": "5000.00",
            "availability": "available",
            "stock_quantity": 5,
            "active_ingredient": "Paracétamol",
            "dosage": "500 mg",
            "pharmaceutical_form": "Comprimé",
            "packaging": "Boîte de 10",
            "requires_prescription": True,
            "authorization_reference": reference,
        }
        payload.update(extra)
        response = self.partner_client.post("/api/v1/partner/products/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def submit(self, product_id):
        return self.partner_client.post(f"/api/v1/partner/products/{product_id}/submit/", {}, format="json")

    def approve(self, product_id):
        return self.admin_client.post(f"/api/v1/admin/marketplace/products/{product_id}/approve/", {}, format="json")

    def verify(self, product_id):
        return self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product_id}/authorization/verify/", {}, format="json"
        )

    def reject(self, product_id, reason):
        return self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product_id}/authorization/reject/",
            {"reason": reason},
            format="json",
        )

    def test_partner_cannot_set_status_or_verify_an_amm(self):
        data = self.create_medicine(
            "Médicament AMM verrouillé",
            "AMM-SEC-001",
            authorization_status="verified",
            authorization_verified_reference="AMM-INVENTEE",
            authorization_decision_tracked=True,
        )
        product = CatalogProduct.objects.get(pk=data["id"])
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.PENDING)
        self.assertEqual(product.authorization_verified_reference, "")
        self.assertFalse(product.authorization_decision_tracked)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="marketplace.authorization.declared", target_id=str(product.pk)
            ).exists()
        )

        patch = self.partner_client.patch(
            f"/api/v1/partner/products/{product.pk}/",
            {"authorization_status": "verified", "authorization_verified_reference": "AMM-INVENTEE"},
            format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        product.refresh_from_db()
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.PENDING)

        self.assertEqual(
            self.partner_client.post(
                f"/api/v1/admin/marketplace/products/{product.pk}/authorization/verify/", {}, format="json"
            ).status_code,
            403,
        )
        self.assertIn(
            self.public_client.post(
                f"/api/v1/admin/marketplace/products/{product.pk}/authorization/verify/", {}, format="json"
            ).status_code,
            (401, 403),
        )

    def test_admin_verification_is_required_before_publication(self):
        data = self.create_medicine("Médicament AMM vérifiable", "AMM-SEC-002")
        product_id = data["id"]
        self.assertEqual(self.submit(product_id).status_code, 200)

        blocked = self.admin_client.patch(
            f"/api/v1/marketplace/admin/products/{product_id}/", {"status": "published"}, format="json"
        )
        self.assertEqual(blocked.status_code, 400, blocked.content)
        self.assertIn("authorization_status", blocked.json()["error"]["details"])

        queue = self.admin_client.get("/api/v1/admin/marketplace/authorizations/")
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertIn(product_id, [item["id"] for item in queue.json()["results"]])

        verified = self.verify(product_id)
        self.assertEqual(verified.status_code, 200, verified.content)
        product = CatalogProduct.objects.get(pk=product_id)
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.VERIFIED)
        self.assertEqual(product.authorization_verified_reference, "AMM-SEC-002")
        self.assertEqual(product.authorization_reviewed_by, self.admin)
        self.assertIsNotNone(product.authorization_reviewed_at)
        self.assertTrue(product.authorization_decision_tracked)

        approved = self.approve(product_id)
        self.assertEqual(approved.status_code, 200, approved.content)
        public = self.public_client.get("/api/v1/marketplace/public/medicines/")
        self.assertEqual(public.json()["count"], 1)
        self.assertNotIn("authorization_reference", public.json()["results"][0])
        self.assertTrue(
            AuditEvent.objects.filter(
                action="marketplace.authorization.verified", target_id=str(product_id)
            ).exists()
        )

    def test_admin_can_reject_an_amm_and_publication_stays_blocked(self):
        data = self.create_medicine("Médicament AMM refusable", "AMM-SEC-003")
        product_id = data["id"]
        self.assertEqual(self.submit(product_id).status_code, 200)

        rejected = self.reject(product_id, "Référence non conforme au registre.")
        self.assertEqual(rejected.status_code, 200, rejected.content)
        product = CatalogProduct.objects.get(pk=product_id)
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.REJECTED)
        self.assertEqual(product.authorization_review_notes, "Référence non conforme au registre.")
        self.assertEqual(product.authorization_verified_reference, "")
        self.assertTrue(product.authorization_decision_tracked)

        blocked = self.approve(product_id)
        self.assertEqual(blocked.status_code, 400, blocked.content)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="marketplace.authorization.rejected", target_id=str(product_id)
            ).exists()
        )

    def test_partner_reference_change_reopens_moderation_and_clears_decision(self):
        data = self.create_medicine("Médicament AMM modifiable", "AMM-SEC-004")
        product_id = data["id"]
        self.assertEqual(self.submit(product_id).status_code, 200)
        self.assertEqual(self.verify(product_id).status_code, 200)
        self.assertEqual(self.approve(product_id).status_code, 200)

        changed = self.partner_client.patch(
            f"/api/v1/partner/products/{product_id}/",
            {"authorization_reference": "AMM-SEC-004-BIS"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        product = CatalogProduct.objects.get(pk=product_id)
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.PENDING)
        self.assertEqual(product.authorization_reference, "AMM-SEC-004-BIS")
        self.assertEqual(product.authorization_verified_reference, "")
        self.assertFalse(product.authorization_decision_tracked)
        self.assertEqual(product.status, CatalogProduct.Status.DRAFT)
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.PENDING)
        self.assertEqual(self.public_client.get("/api/v1/marketplace/public/medicines/").json()["count"], 0)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="marketplace.authorization.declared", target_id=str(product_id)
            ).count()
            >= 2
        )

        self.assertEqual(self.verify(product_id).status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.authorization_verified_reference, "AMM-SEC-004-BIS")
        self.assertEqual(self.approve(product_id).status_code, 200)
        self.assertEqual(self.public_client.get("/api/v1/marketplace/public/medicines/").json()["count"], 1)
