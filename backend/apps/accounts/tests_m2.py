from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from apps.reference.models import Country

from .models import ProfessionalVerificationRequest

User = get_user_model()

ADMIN_ENDPOINTS = (
    ("get", "/api/v1/admin/dashboard/"),
    ("get", "/api/v1/admin/accounts/"),
    ("get", "/api/v1/admin/professional-verifications/"),
    ("post", "/api/v1/admin/professional-verifications/999999/review/"),
    ("get", "/api/v1/marketplace/admin/sellers/"),
    ("get", "/api/v1/marketplace/admin/products/"),
    ("get", "/api/v1/marketplace/admin/options/"),
    ("get", "/api/v1/marketplace/admin/products/999999/image/"),
    ("get", "/api/v1/admin/marketplace/moderation/"),
    ("get", "/api/v1/admin/marketplace/authorizations/"),
    ("post", "/api/v1/admin/marketplace/products/999999/approve/"),
    ("post", "/api/v1/admin/marketplace/products/999999/reject/"),
    ("post", "/api/v1/admin/marketplace/products/999999/authorization/verify/"),
    ("get", "/api/v1/admin/marketplace/products/999999/price-history/"),
    ("post", "/api/v1/admin/marketplace/sellers/999999/assign-owner/"),
    ("get", "/api/v1/site-content/admin/faqs/"),
    ("get", "/api/v1/site-content/admin/news/"),
    ("get", "/api/v1/site-content/admin/pages/"),
    ("get", "/api/v1/site-content/admin/images/"),
    ("get", "/api/v1/site-content/admin/configuration/"),
    ("get", "/api/v1/promotions/admin/"),
    ("post", "/api/v1/promotions/admin/999999/approve/"),
    ("post", "/api/v1/promotions/admin/999999/reject/"),
    ("post", "/api/v1/promotions/admin/999999/archive/"),
    ("get", "/api/v1/admin/orders/"),
    ("get", "/api/v1/professionals/admin/profiles/"),
)


class CentralAdminPermissionTests(TestCase):
    def create_client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def grant(self, user, *labels):
        for label in labels:
            app_label, codename = label.split(".", 1)
            permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            user.user_permissions.add(permission)
        return User.objects.get(pk=user.pk)

    def call(self, client, method, path):
        return getattr(client, method)(path, {}, format="json")

    def test_plain_staff_is_denied_on_every_admin_endpoint(self):
        staff = User.objects.create_user(username="plain-staff", password="Strong-Permission-Password-928!", is_staff=True)
        client = self.create_client(staff)

        for method, path in ADMIN_ENDPOINTS:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.call(client, method, path).status_code, 403)

    def test_partner_with_model_permission_is_still_denied(self):
        partner = User.objects.create_user(username="partner-with-perm", password="Strong-Permission-Password-928!")
        partner = self.grant(partner, "accounts.view_accountprofile", "marketplace.view_catalogproduct")
        client = self.create_client(partner)

        self.assertEqual(client.get("/api/v1/admin/dashboard/").status_code, 403)
        self.assertEqual(client.get("/api/v1/marketplace/admin/products/").status_code, 403)

    def test_superuser_keeps_access_to_every_admin_endpoint(self):
        admin = User.objects.create_superuser(
            username="central-superuser",
            email="central-superuser@example.test",
            password="Strong-Permission-Password-928!",
        )
        client = self.create_client(admin)

        for method, path in ADMIN_ENDPOINTS:
            with self.subTest(method=method, path=path):
                self.assertNotEqual(self.call(client, method, path).status_code, 403)

    def test_superuser_without_is_staff_flag_keeps_api_access(self):
        admin = User.objects.create_superuser(
            username="superuser-not-staff",
            email="superuser-not-staff@example.test",
            password="Strong-Permission-Password-928!",
        )
        admin.is_staff = False
        admin.save(update_fields=("is_staff",))
        client = self.create_client(admin)
        self.assertNotEqual(client.get("/api/v1/admin/dashboard/").status_code, 403)

    def test_staff_permission_is_limited_to_its_feature(self):
        staff = User.objects.create_user(username="scoped-staff", password="Strong-Permission-Password-928!", is_staff=True)
        staff = self.grant(staff, "accounts.view_accountprofile")
        client = self.create_client(staff)

        self.assertEqual(client.get("/api/v1/admin/dashboard/").status_code, 200)
        self.assertEqual(client.get("/api/v1/admin/accounts/").status_code, 200)
        self.assertEqual(client.get("/api/v1/admin/orders/").status_code, 403)

    def test_action_based_permissions_separate_read_and_write(self):
        staff = User.objects.create_user(username="product-staff", password="Strong-Permission-Password-928!", is_staff=True)
        staff = self.grant(staff, "marketplace.view_catalogproduct")
        client = self.create_client(staff)

        self.assertEqual(client.get("/api/v1/marketplace/admin/products/").status_code, 200)
        self.assertEqual(client.post("/api/v1/marketplace/admin/products/", {}, format="json").status_code, 403)

        staff = self.grant(staff, "marketplace.add_catalogproduct")
        client = self.create_client(staff)
        self.assertNotEqual(client.post("/api/v1/marketplace/admin/products/", {}, format="json").status_code, 403)

    def test_method_based_permissions_separate_read_and_write(self):
        staff = User.objects.create_user(username="site-staff", password="Strong-Permission-Password-928!", is_staff=True)
        staff = self.grant(staff, "sitecontent.view_siteconfiguration")
        client = self.create_client(staff)

        self.assertEqual(client.get("/api/v1/site-content/admin/configuration/").status_code, 200)
        self.assertEqual(client.patch("/api/v1/site-content/admin/configuration/", {}, format="json").status_code, 403)

        staff = self.grant(staff, "sitecontent.change_siteconfiguration")
        client = self.create_client(staff)
        self.assertNotEqual(client.patch("/api/v1/site-content/admin/configuration/", {}, format="json").status_code, 403)

    def test_verification_review_requires_change_permission(self):
        staff = User.objects.create_user(username="review-staff", password="Strong-Permission-Password-928!", is_staff=True)
        staff = self.grant(staff, "accounts.view_professionalverificationrequest")
        client = self.create_client(staff)

        applicant = User.objects.create_user(username="applicant-m2", password="Strong-Permission-Password-928!")
        verification = ProfessionalVerificationRequest.objects.create(
            user=applicant,
            category=ProfessionalVerificationRequest.Category.DOCTOR,
            organization_name="Cabinet test",
            country=Country.objects.get(code_alpha2="MG"),
        )

        self.assertEqual(client.get("/api/v1/admin/professional-verifications/").status_code, 200)
        self.assertEqual(client.post(f"/api/v1/admin/professional-verifications/{verification.pk}/review/", {}, format="json").status_code, 403)

        staff = self.grant(staff, "accounts.change_professionalverificationrequest")
        client = self.create_client(staff)
        self.assertNotEqual(client.post(f"/api/v1/admin/professional-verifications/{verification.pk}/review/", {}, format="json").status_code, 403)

    def test_existing_professionals_permissions_still_work(self):
        staff = User.objects.create_user(username="professionals-staff", password="Strong-Permission-Password-928!", is_staff=True)
        staff = self.grant(staff, "professionals.view_professionalprofile")
        client = self.create_client(staff)
        self.assertEqual(client.get("/api/v1/professionals/admin/profiles/").status_code, 200)
