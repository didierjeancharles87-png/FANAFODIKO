from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.reference.models import Country

from .models import AccountProfile, ProfessionalVerificationRequest

User = get_user_model()


def grant_permission(user, label):
    app_label, codename = label.split(".", 1)
    user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return User.objects.get(pk=user.pk)


class AccountAndVerificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="applicant", password="Safe-test-password-928", email="applicant@example.test")
        self.country = Country.objects.get(code_alpha2="MG")
        self.client = APIClient()

    def test_anonymous_user_cannot_submit_verification(self):
        response = self.client.post("/api/v1/accounts/professional-verifications/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["status"], 403)

    def test_authenticated_user_can_submit_and_list_own_request(self):
        self.client.force_authenticate(self.user)
        payload = {
            "category": "doctor",
            "organization_name": "  Cabinet   Analamanga ",
            "license_number": " MG-1024 ",
            "country": self.country.pk,
        }
        created = self.client.post("/api/v1/accounts/professional-verifications/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["organization_name"], "Cabinet Analamanga")
        self.assertEqual(created.json()["license_number"], "MG-1024")
        self.assertEqual(created.json()["status"], ProfessionalVerificationRequest.Status.PENDING)
        self.assertTrue(self.user.groups.filter(name="professional_pending").exists())
        self.assertTrue(AuditEvent.objects.filter(action="professional_verification.submitted", actor=self.user).exists())

        own_requests = self.client.get("/api/v1/accounts/professional-verifications/")
        self.assertEqual(own_requests.status_code, 200)
        self.assertEqual(len(own_requests.json()), 1)

    def test_invalid_values_and_duplicate_pending_requests_are_rejected(self):
        self.client.force_authenticate(self.user)
        invalid = self.client.post("/api/v1/accounts/professional-verifications/", {"category": "invented"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("details", invalid.json()["error"])

        payload = {"category": "pharmacy", "organization_name": "Pharmacie A", "license_number": "PHA-1", "country": self.country.pk}
        first = self.client.post("/api/v1/accounts/professional-verifications/", payload, format="json")
        second = self.client.post("/api/v1/accounts/professional-verifications/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)

    def test_suspended_account_cannot_use_account_api(self):
        self.user.account_profile.status = AccountProfile.Status.SUSPENDED
        self.user.account_profile.save()
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/v1/accounts/professional-verifications/")

        self.assertEqual(response.status_code, 403)

    def test_session_mutation_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(username="applicant", password="Safe-test-password-928"))
        payload = {"category": "clinic", "organization_name": "Clinique A", "license_number": "CL-7", "country": self.country.pk}

        denied = client.post("/api/v1/accounts/professional-verifications/", payload, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(ProfessionalVerificationRequest.objects.count(), 0)

        client.get("/admin/login/")
        token = client.cookies["csrftoken"].value
        accepted = client.post(
            "/api/v1/accounts/professional-verifications/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 201, accepted.content)

    def test_role_groups_are_seeded(self):
        self.assertTrue(Group.objects.filter(name="patient").exists())
        self.assertTrue(Group.objects.filter(name="professional_pending").exists())
        self.assertTrue(Group.objects.filter(name="professional_verified").exists())


class AdminAPIAndReviewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="admin-staff", password="Safe-test-password-928", email="admin@example.test", is_staff=True)
        self.staff = grant_permission(self.staff, "accounts.view_accountprofile")
        self.staff = grant_permission(self.staff, "accounts.change_professionalverificationrequest")
        self.applicant = User.objects.create_user(username="professional", password="Safe-test-password-928", email="professional@example.test")
        self.request = ProfessionalVerificationRequest.objects.create(
            user=self.applicant,
            category="dentist",
            organization_name="Cabinet dentaire",
            license_number="DEN-88",
            country=Country.objects.get(code_alpha2="MG"),
        )
        self.client = APIClient()

    def test_non_staff_cannot_access_dashboard(self):
        self.client.force_authenticate(self.applicant)
        response = self.client.get("/api/v1/admin/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_staff_dashboard_uses_current_data(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get("/api/v1/admin/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["professional_verifications"]["pending"], 1)
        self.assertGreaterEqual(response.json()["users"]["total"], 2)

    def test_staff_can_review_request_and_review_is_audited(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.request.pk}/review/",
            {"status": "approved", "notes": "Licence contrôlée"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ProfessionalVerificationRequest.Status.APPROVED)
        self.assertEqual(self.request.reviewed_by, self.staff)
        self.assertFalse(self.applicant.groups.filter(name="professional_pending").exists())
        self.assertTrue(self.applicant.groups.filter(name="professional_verified").exists())
        self.assertTrue(AuditEvent.objects.filter(action="professional_verification.approved", actor=self.staff).exists())

    def test_applicant_cannot_review_own_request(self):
        self.request.user.is_staff = True
        self.request.user.save(update_fields=("is_staff",))
        self.applicant = grant_permission(self.applicant, "accounts.change_professionalverificationrequest")
        self.client.force_authenticate(self.applicant)
        response = self.client.post(
            f"/api/v1/admin/professional-verifications/{self.request.pk}/review/",
            {"status": "approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ProfessionalVerificationRequest.Status.PENDING)

    def test_admin_dashboard_renders_metrics_from_live_models(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indicateurs de la plateforme")
        self.assertContains(response, "Validations en attente")

    def test_suspended_staff_cannot_enter_admin(self):
        self.staff.account_profile.status = AccountProfile.Status.SUSPENDED
        self.staff.account_profile.save()
        self.client.force_login(self.staff)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)


class PatientAccountAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get(code_alpha2="MG")

    def patient_payload(self):
        return {
            "email": "patient@example.test",
            "password": "A-Strong-Patient-Password-928!",
            "first_name": "Miora",
            "last_name": "Rakoto",
            "phone_number": "+261 34 12 345 67",
            "country": self.country.pk,
        }

    def test_registration_uses_patient_role_and_opens_session(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        response = client.post("/api/v1/auth/register-patient/", self.patient_payload(), format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(email="patient@example.test")
        self.assertTrue(user.groups.filter(name="patient").exists())
        self.assertEqual(user.account_profile.phone_number, "+261 34 12 345 67")
        self.assertEqual(response.json()["roles"], ["patient"])
        self.assertEqual(client.get("/api/v1/accounts/patient/profile/").status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="patient_registration.created", actor=user).exists())

    def test_registration_rejects_duplicates_weak_password_and_requires_csrf(self):
        payload = self.patient_payload()
        csrf_client = APIClient(enforce_csrf_checks=True)
        denied = csrf_client.post("/api/v1/auth/register-patient/", payload, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(User.objects.count(), 0)

        csrf_client.get("/api/v1/auth/csrf/")
        csrf = csrf_client.cookies["csrftoken"].value
        weak = {**payload, "password": "password"}
        invalid = csrf_client.post("/api/v1/auth/register-patient/", weak, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("password", invalid.json()["error"]["details"])
        self.assertEqual(User.objects.count(), 0)

        created = csrf_client.post("/api/v1/auth/register-patient/", payload, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(created.status_code, 201, created.content)
        duplicate = APIClient(enforce_csrf_checks=True)
        duplicate.get("/api/v1/auth/csrf/")
        duplicate_csrf = duplicate.cookies["csrftoken"].value
        response = duplicate.post("/api/v1/auth/register-patient/", payload, format="json", HTTP_X_CSRFTOKEN=duplicate_csrf)
        self.assertEqual(response.status_code, 400)

    def test_patient_can_update_only_personal_profile_fields(self):
        patient = User.objects.create_user(username="p@example.test", email="p@example.test", password="A-Strong-Patient-Password-928!")
        patient.groups.add(Group.objects.get(name="patient"))
        patient.account_profile.country = self.country
        patient.account_profile.save()
        self.client.force_authenticate(patient)
        changed = self.client.patch("/api/v1/accounts/patient/profile/", {"first_name": "Soa", "phone_number": "+261 34 99 888 77", "email": "attacker@example.test"}, format="json")
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["first_name"], "Soa")
        self.assertEqual(changed.json()["email"], "attacker@example.test")
        self.assertEqual(changed.json()["country"], self.country.pk)
        patient.refresh_from_db()
        self.assertEqual(patient.email, "attacker@example.test")
        self.assertEqual(patient.username, "attacker@example.test")
        self.assertEqual(patient.account_profile.phone_number, "+261 34 99 888 77")
        self.assertTrue(AuditEvent.objects.filter(action="patient_profile.updated", actor=patient).exists())
        invalid = self.client.patch("/api/v1/accounts/patient/profile/", {"phone_number": "pas un téléphone"}, format="json")
        self.assertEqual(invalid.status_code, 400)

    def test_non_patient_cannot_read_patient_profile_and_login_logout_reuse_shared_session(self):
        professional = User.objects.create_user(username="pro@example.test", email="pro@example.test", password="A-Strong-Patient-Password-928!")
        self.client.force_authenticate(professional)
        self.assertEqual(self.client.get("/api/v1/accounts/patient/profile/").status_code, 403)

        patient = User.objects.create_user(username="login@example.test", email="login@example.test", password="A-Strong-Patient-Password-928!")
        patient.groups.add(Group.objects.get(name="patient"))
        client = APIClient()
        csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        logged_in = client.post("/api/v1/auth/login/", {"email": patient.email, "password": "A-Strong-Patient-Password-928!"}, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(logged_in.status_code, 200, logged_in.content)
        self.assertIn("patient", logged_in.json()["roles"])
        self.assertEqual(client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf).status_code, 204)
