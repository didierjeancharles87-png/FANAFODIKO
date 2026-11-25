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

from .models import CatalogProduct, CatalogSeller, SellerOwner

User = get_user_model()


class Phase7PartnerSecurityTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="phase7-security-admin",
            email="phase7-security-admin@example.test",
            password="Valid-Security-Password-934!",
        )
        self.admin_client = self.client_for(self.admin)

        self.seller_a = self.create_supplier("Vendeur sécurité A", "REF-SEC-A")
        self.seller_b = self.create_supplier("Vendeur sécurité B", "REF-SEC-B")
        self.user_a, self.account_a = self.create_account("phase7-partner-a")
        self.user_b, self.account_b = self.create_account("phase7-partner-b")
        SellerOwner.objects.create(account=self.account_a, seller=self.seller_a)
        SellerOwner.objects.create(account=self.account_b, seller=self.seller_b)
        self.product_a = self.create_product(self.seller_a, "Produit du partenaire A")
        self.product_b = self.create_product(self.seller_b, "Produit du partenaire B")

        self.client_a = self.client_for(self.user_a)
        self.client_b = self.client_for(self.user_b)
        self.user_ordinary, self.account_ordinary = self.create_account("phase7-ordinary")
        self.client_ordinary = self.client_for(self.user_ordinary)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_account(self, username, status=AccountProfile.Status.ACTIVE):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Valid-Security-Password-934!",
        )
        account, _ = AccountProfile.objects.get_or_create(user=user)
        if status != AccountProfile.Status.ACTIVE:
            account.status = status
            account.save(update_fields=("status", "updated_at"))
        return user, account

    def create_supplier(self, name, reference):
        return CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name=name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
            verification_reference=reference,
        )

    def create_product(self, seller, title):
        return CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title=title,
            seller=seller,
            price_mga=Decimal("15000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            status=CatalogProduct.Status.DRAFT,
            equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
            stock_quantity=4,
        )

    def create_pharmacy_profile(self, username, verified):
        user, account = self.create_account(username)
        profile = ProfessionalProfile.objects.create(
            account=account,
            category=ProfessionalCategory.PHARMACY,
            legal_name=f"Pharmacie {username}",
            country=self.country,
            city="Antananarivo",
        )
        if verified:
            profile.verification_status = ProfessionalProfile.VerificationStatus.APPROVED
            profile.save(update_fields=("verification_status", "updated_at"))
            user.groups.add(Group.objects.get(name="professional_verified"))
        else:
            profile.verification_status = ProfessionalProfile.VerificationStatus.PENDING
            profile.save(update_fields=("verification_status", "updated_at"))
        return user, account, profile

    def create_pharmacy_seller(self, profile):
        return CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.PHARMACY,
            professional_profile=profile,
            name=profile.legal_name,
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
        )

    def assign(self, seller, account, client=None):
        return (client or self.admin_client).post(
            f"/api/v1/admin/marketplace/sellers/{seller.pk}/assign-owner/",
            {"account": account.pk},
            format="json",
        )

    def test_partner_a_reads_only_own_seller_and_products(self):
        seller_response = self.client_a.get(f"/api/v1/partner/sellers/{self.seller_a.pk}/")
        self.assertEqual(seller_response.status_code, 200, seller_response.content)
        self.assertEqual(seller_response.json()["id"], self.seller_a.pk)

        list_response = self.client_a.get("/api/v1/partner/products/")
        self.assertEqual(list_response.status_code, 200, list_response.content)
        product_ids = {item["id"] for item in list_response.json()["results"]}
        self.assertIn(self.product_a.pk, product_ids)
        self.assertNotIn(self.product_b.pk, product_ids)

        detail_response = self.client_a.get(f"/api/v1/partner/products/{self.product_a.pk}/")
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["seller"], self.seller_a.pk)

    def test_partner_a_gets_404_for_seller_b_and_product_b(self):
        seller_response = self.client_a.get(f"/api/v1/partner/sellers/{self.seller_b.pk}/")
        self.assertEqual(seller_response.status_code, 404, seller_response.content)

        product_response = self.client_a.get(f"/api/v1/partner/products/{self.product_b.pk}/")
        self.assertEqual(product_response.status_code, 404, product_response.content)

        other_partner_response = self.client_b.get(f"/api/v1/partner/sellers/{self.seller_a.pk}/")
        self.assertEqual(other_partner_response.status_code, 404, other_partner_response.content)

    def test_partner_a_cannot_modify_or_delete_product_b(self):
        original_title = self.product_b.title
        patch_response = self.client_a.patch(
            f"/api/v1/partner/products/{self.product_b.pk}/",
            {"title": "Titre modifié sans autorisation"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 404, patch_response.content)

        delete_response = self.client_a.delete(f"/api/v1/partner/products/{self.product_b.pk}/")
        self.assertEqual(delete_response.status_code, 404, delete_response.content)

        self.product_b.refresh_from_db()
        self.assertEqual(self.product_b.title, original_title)

        own_response = self.client_a.patch(
            f"/api/v1/partner/products/{self.product_a.pk}/",
            {"title": "Modification autorisée"},
            format="json",
        )
        self.assertEqual(own_response.status_code, 200, own_response.content)
        self.assertEqual(own_response.json()["title"], "Modification autorisée")

    def test_suspended_account_cannot_manage_seller(self):
        self.account_a.status = AccountProfile.Status.SUSPENDED
        self.account_a.save(update_fields=("status", "updated_at"))

        seller_response = self.client_a.get(f"/api/v1/partner/sellers/{self.seller_a.pk}/")
        self.assertEqual(seller_response.status_code, 403, seller_response.content)

        product_response = self.client_a.get(f"/api/v1/partner/products/{self.product_a.pk}/")
        self.assertEqual(product_response.status_code, 403, product_response.content)

    def test_unassigned_account_cannot_access_partner_space(self):
        seller_response = self.client_ordinary.get(f"/api/v1/partner/sellers/{self.seller_a.pk}/")
        self.assertEqual(seller_response.status_code, 403, seller_response.content)

        products_response = self.client_ordinary.get("/api/v1/partner/products/")
        self.assertEqual(products_response.status_code, 403, products_response.content)

    def test_ordinary_user_cannot_assign_owner(self):
        seller = self.create_supplier("Vendeur non attribué", "REF-SEC-ORDINARY")
        before = SellerOwner.objects.count()

        response = self.assign(seller, self.account_ordinary, client=self.client_ordinary)
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(SellerOwner.objects.count(), before)
        self.assertFalse(SellerOwner.objects.filter(seller=seller).exists())

    def test_authorized_admin_can_assign_owner_once_and_audits(self):
        seller = self.create_supplier("Vendeur à attribuer", "REF-SEC-ASSIGN")
        _, target_account = self.create_account("phase7-assigned-owner")

        response = self.assign(seller, target_account)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["seller"], seller.pk)
        self.assertEqual(response.json()["account"], target_account.pk)
        self.assertTrue(SellerOwner.objects.filter(seller=seller, account=target_account).exists())

        audit = AuditEvent.objects.get(action="marketplace.seller_owner.assigned")
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.target_type, "marketplace.sellerowner")
        self.assertEqual(audit.metadata["seller_id"], seller.pk)

        duplicate = self.assign(seller, self.account_ordinary)
        self.assertEqual(duplicate.status_code, 400, duplicate.content)
        self.assertIn("seller", duplicate.json()["error"]["details"])
        self.assertEqual(SellerOwner.objects.filter(seller=seller).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="marketplace.seller_owner.assigned").count(), 1)

    def test_inactive_target_account_cannot_be_assigned(self):
        seller = self.create_supplier("Vendeur cible inactive", "REF-SEC-INACTIVE")
        _, target_account = self.create_account("phase7-inactive-owner", status=AccountProfile.Status.SUSPENDED)

        response = self.assign(seller, target_account)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("account", response.json()["error"]["details"])
        self.assertFalse(SellerOwner.objects.filter(seller=seller).exists())

    def test_unapproved_pharmacy_profile_cannot_be_assigned(self):
        _, _, approved_profile = self.create_pharmacy_profile("phase7-pharma-approved", verified=True)
        seller = self.create_pharmacy_seller(approved_profile)
        _, unapproved_account, _ = self.create_pharmacy_profile("phase7-pharma-pending", verified=False)

        response = self.assign(seller, unapproved_account)
        self.assertEqual(response.status_code, 400, response.content)
        details = response.json()["error"]["details"]
        self.assertIn("account", details)
        self.assertFalse(SellerOwner.objects.filter(seller=seller).exists())

    def test_approved_pharmacy_profile_can_be_assigned(self):
        _, approved_account, approved_profile = self.create_pharmacy_profile("phase7-pharma-owner", verified=True)
        seller = self.create_pharmacy_seller(approved_profile)

        response = self.assign(seller, approved_account)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(SellerOwner.objects.filter(seller=seller, account=approved_account).exists())
