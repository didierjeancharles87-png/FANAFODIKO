from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import ProfessionalVerificationRequest
from apps.audit.models import AuditEvent
from apps.reference.models import Country

from .models import ProfessionalDocument, ProfessionalProfile

User = get_user_model()


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    return client


class ProfessionalRegistrationTests(TestCase):
    def test_professional_category_endpoint_is_public_and_returns_all_six_categories(self):
        response = APIClient().get("/api/v1/professionals/categories/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            [
                {"code": "pharmacy", "label": "Pharmacie"},
                {"code": "doctor", "label": "Médecin"},
                {"code": "dentist", "label": "Dentiste"},
                {"code": "laboratory", "label": "Laboratoire d’analyses médicales"},
                {"code": "delivery_courier", "label": "Livreur indépendant"},
                {"code": "delivery_company", "label": "Société de livraison"},
            ],
        )

    def test_registration_supports_each_required_professional_category(self):
        categories = ("pharmacy", "doctor", "dentist", "laboratory", "delivery_courier", "delivery_company")
        for category in categories:
            client = csrf_client()
            payload = {
                "email": f"{category}@example.test",
                "password": "R3ally-Strong-Professional-Password!",
                "category": category,
                "legal_name": f"Test {category}",
                "contact_phone": "+261 20 00 000 00",
            }
            response = client.post("/api/v1/auth/register/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()["category"], category)
            self.assertEqual(response.json()["verification_status"], ProfessionalProfile.VerificationStatus.DRAFT)
            current_user = client.get("/api/v1/auth/me/")
            self.assertEqual(current_user.status_code, 200)
            self.assertTrue(current_user.json()["professional_profile_id"])

        self.assertEqual(ProfessionalProfile.objects.count(), 6)
        self.assertEqual(AuditEvent.objects.filter(action="professional_registration.created").count(), 6)

    def test_registration_accepts_an_omitted_optional_phone(self):
        client = csrf_client()
        payload = {
            "email": "without-phone@example.test",
            "password": "R3ally-Strong-Professional-Password!",
            "category": "doctor",
            "legal_name": "Cabinet sans téléphone",
        }
        response = client.post("/api/v1/auth/register/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["contact_phone"], "")

    def test_registration_returns_field_specific_phone_error(self):
        client = csrf_client()
        payload = {
            "email": "invalid-fields@example.test",
            "password": "R3ally-Strong-Professional-Password!",
            "category": "doctor",
            "legal_name": "Cabinet test",
            "contact_phone": "not a phone number",
        }
        response = client.post("/api/v1/auth/register/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

        self.assertEqual(response.status_code, 400)
        details = response.json()["error"]["details"]
        self.assertIn("contact_phone", details)
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())
        self.assertEqual(ProfessionalProfile.objects.count(), 0)

    def test_registration_returns_field_specific_password_error(self):
        client = csrf_client()
        payload = {
            "email": "weak-password@example.test",
            "password": "password",
            "category": "doctor",
            "legal_name": "Cabinet test",
        }
        response = client.post("/api/v1/auth/register/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["details"])
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())
        self.assertEqual(ProfessionalProfile.objects.count(), 0)

    def test_category_specific_profile_details_validate_for_all_six_categories(self):
        detail_payloads = {
            "pharmacy": {"commercial_name": "Pharmacie Test", "opening_hours": {"monday": [{"open": "08:00", "close": "17:00"}]}},
            "doctor": {"specialty": "Médecine générale", "establishment_name": "Cabinet Test"},
            "dentist": {"specialty": "Dentisterie", "establishment_name": "Cabinet dentaire"},
            "laboratory": {"services": ["Hématologie", "Biochimie"]},
            "delivery_courier": {"service_areas": [{"country_code": "MG", "region": "Analamanga", "city": "Antananarivo"}], "delivery_types": ["Documents"], "transport_modes": ["Vélo"]},
            "delivery_company": {"service_areas": [{"country_code": "MG", "region": "Analamanga", "city": "Antananarivo"}], "delivery_types": ["Colis"], "transport_modes": ["Camionnette"]},
        }
        for category, details in detail_payloads.items():
            user = User.objects.create_user(username=f"{category}-details", password="R3ally-Strong-Professional-Password!")
            ProfessionalProfile.objects.create(account=user.account_profile, category=category, legal_name=f"Profil {category}")
            client = APIClient(); client.force_authenticate(user)
            response = client.patch("/api/v1/professionals/me/", {"details": details}, format="json")
            self.assertEqual(response.status_code, 200, f"{category}: {response.content}")
            for field, value in details.items():
                self.assertEqual(response.json()["details"][field], value)

    def test_registration_requires_csrf_and_password_validation(self):
        client = APIClient(enforce_csrf_checks=True)
        payload = {"email": "new@example.test", "password": "password", "category": "doctor", "legal_name": "Cabinet"}
        no_csrf = client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(no_csrf.status_code, 403)

        client.get("/api/v1/auth/csrf/")
        weak_password = client.post("/api/v1/auth/register/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(weak_password.status_code, 400)
        self.assertIn("password", weak_password.json()["error"]["details"])
        self.assertFalse(User.objects.filter(email="new@example.test").exists())

    def test_login_and_current_session(self):
        User.objects.create_user(username="login@example.test", email="login@example.test", password="R3ally-Strong-Professional-Password!")
        client = csrf_client()
        response = client.post(
            "/api/v1/auth/login/",
            {"email": "login@example.test", "password": "R3ally-Strong-Professional-Password!"},
            format="json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)


class ProfessionalProfileAndDocumentTests(TestCase):
    def setUp(self):
        self.client = csrf_client()
        response = self.client.post(
            "/api/v1/auth/register/",
            {"email": "doctor@example.test", "password": "R3ally-Strong-Professional-Password!", "category": "doctor", "legal_name": "Cabinet médical"},
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.profile = ProfessionalProfile.objects.get(account__user__email="doctor@example.test")
        self.country = Country.objects.get(code_alpha2="MG")

    def complete_profile(self):
        return self.patch_profile({
            "manager_name": "Dr Test",
            "contact_phone": "+261 20 00 000 00",
            "contact_email": "doctor@example.test",
            "country": self.country.pk,
            "region": "Analamanga",
            "city": "Antananarivo",
            "address": "Lot 1, Analamanga",
            "details": {"specialty": "Médecine générale", "establishment_name": "Cabinet Test", "registration_number": "REG-1", "availability_info": "Lundi à vendredi"},
        })

    def test_incomplete_pharmacy_profile_can_be_read_and_updated_without_optional_details(self):
        pharmacy_user = User.objects.create_user(username="new-pharmacy", password="R3ally-Strong-Professional-Password!")
        pharmacy = ProfessionalProfile.objects.create(
            account=pharmacy_user.account_profile,
            category="pharmacy",
            legal_name="Pharmacie incomplète",
        )
        client = APIClient()
        client.force_authenticate(pharmacy_user)

        read = client.get("/api/v1/professionals/me/")
        self.assertEqual(read.status_code, 200, read.content)
        self.assertEqual(read.json()["details"], {})
        self.assertCountEqual(
            read.json()["missing_information"],
            ["manager_name", "contact_phone", "contact_email", "country", "region", "city", "address", "commercial_name", "opening_hours", "supporting_document"],
        )

        updated = client.patch(
            "/api/v1/professionals/me/",
            {"manager_name": "Responsable test", "details": {"commercial_name": "Pharmacie test"}},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["manager_name"], "Responsable test")
        self.assertEqual(updated.json()["details"]["commercial_name"], "Pharmacie test")
        pharmacy.refresh_from_db()
        self.assertEqual(pharmacy.pharmacy_details.commercial_name, "Pharmacie test")

    def patch_profile(self, payload):
        self.client.get("/api/v1/auth/csrf/")
        return self.client.patch(
            "/api/v1/professionals/me/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

    def submit_profile(self):
        self.client.get("/api/v1/auth/csrf/")
        return self.client.post("/api/v1/professionals/me/submit/", {}, format="json", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)

    def upload_document(self, filename="registration.pdf", content=b"%PDF-1.7\nFANAFODIKO test document\n"):
        self.client.get("/api/v1/auth/csrf/")
        return self.client.post(
            "/api/v1/professionals/me/documents/",
            {"document_type": "registration", "file": SimpleUploadedFile(filename, content, content_type="application/pdf")},
            format="multipart",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

    def test_profile_fields_are_validated_and_category_is_immutable(self):
        invalid = self.patch_profile({"latitude": "91"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["status"], 400)

        valid = self.complete_profile()
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(valid.json()["details"]["specialty"], "Médecine générale")
        self.assertNotIn("user_email", valid.json())
        attempted_category_change = self.patch_profile({"category": "pharmacy"})
        self.assertEqual(attempted_category_change.status_code, 200)
        self.assertEqual(attempted_category_change.json()["category"], "doctor")

    def test_document_validation_privacy_and_owner_access(self):
        invalid = self.upload_document("payload.pdf", b"MZ fake executable")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(ProfessionalDocument.objects.count(), 0)

        uploaded = self.upload_document()
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        data = uploaded.json()
        self.assertNotIn("file", data)
        self.assertNotIn("private_media", str(data))
        self.assertIn("/download/", data["download_url"])

        download = self.client.get(data["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.7\nFANAFODIKO test document\n")
        self.assertTrue(AuditEvent.objects.filter(action="professional_document.downloaded").exists())

        another_user = User.objects.create_user(username="other", password="R3ally-Strong-Professional-Password!")
        other_client = APIClient()
        other_client.force_authenticate(another_user)
        self.assertEqual(other_client.get(data["download_url"]).status_code, 404)

    def test_administrator_can_list_and_download_documents_with_audit(self):
        uploaded = self.upload_document()
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        admin_user = User.objects.create_superuser(username="document-admin", email="doc-admin@example.test", password="R3ally-Strong-Professional-Password!")
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)

        listing = admin_client.get("/api/v1/professionals/admin/documents/?category=doctor")
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(listing.json()["count"], 1)
        document_id = listing.json()["results"][0]["id"]
        download = admin_client.get(f"/api/v1/professionals/admin/documents/{document_id}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action="professional_document.downloaded", actor=admin_user).exists())

    def test_rejected_profile_can_be_corrected_and_resubmitted_with_same_license(self):
        self.assertEqual(self.complete_profile().status_code, 200)
        self.assertEqual(self.upload_document().status_code, 201)
        first_submission = self.submit_profile()
        self.assertEqual(first_submission.status_code, 200, first_submission.content)
        self.profile.refresh_from_db()
        rejected_request_id = self.profile.verification_request_id

        admin_user = User.objects.create_superuser(username="rejector", email="rejector@example.test", password="R3ally-Strong-Professional-Password!")
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)
        rejected = admin_client.post(
            f"/api/v1/admin/professional-verifications/{rejected_request_id}/review/",
            {"status": "rejected", "notes": "Préciser la disponibilité"},
            format="json",
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, ProfessionalProfile.VerificationStatus.REJECTED)

        corrected = self.patch_profile({"description": "Informations complétées"})
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(corrected.json()["verification_status"], "draft")
        resubmitted = self.submit_profile()
        self.assertEqual(resubmitted.status_code, 200, resubmitted.content)
        self.assertEqual(resubmitted.json()["verification_status"], "pending")
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.verification_request_id, rejected_request_id)

    def test_submission_requires_complete_profile_and_document_then_links_review(self):
        incomplete = self.submit_profile()
        self.assertEqual(incomplete.status_code, 400)
        self.assertIn("missing_information", incomplete.json()["error"]["details"])

        completed = self.complete_profile()
        self.assertEqual(completed.status_code, 200)
        uploaded = self.upload_document()
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        submitted = self.submit_profile()
        self.assertEqual(submitted.status_code, 200, submitted.content)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, ProfessionalProfile.VerificationStatus.PENDING)
        self.assertEqual(self.profile.verification_request.category, "doctor")
        self.assertEqual(self.profile.verification_request.license_number, "REG-1")
        self.assertTrue(self.profile.account.user.groups.filter(name="professional_pending").exists())

        admin_user = User.objects.create_superuser(username="reviewer", email="reviewer@example.test", password="R3ally-Strong-Professional-Password!")
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)
        reviewed = admin_client.post(
            f"/api/v1/admin/professional-verifications/{self.profile.verification_request_id}/review/",
            {"status": "approved", "notes": "Pièces vérifiées"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, ProfessionalProfile.VerificationStatus.APPROVED)
        self.assertTrue(self.profile.account.user.groups.filter(name="professional_verified").exists())
        self.assertTrue(AuditEvent.objects.filter(action="professional_profile.approved").exists())

    def test_admin_permissions_control_professional_listing_and_suspension(self):
        staff = User.objects.create_user(username="limited-staff", password="R3ally-Strong-Professional-Password!", is_staff=True)
        staff_client = APIClient()
        staff_client.force_authenticate(staff)
        self.assertEqual(staff_client.get("/api/v1/professionals/admin/profiles/").status_code, 403)

        admin_user = User.objects.create_superuser(username="platform-admin", email="platform@example.test", password="R3ally-Strong-Professional-Password!")
        admin_client = APIClient()
        admin_client.force_authenticate(admin_user)
        listing = admin_client.get("/api/v1/professionals/admin/profiles/?category=doctor&status=draft")
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(listing.json()["count"], 1)

        suspended = admin_client.post(f"/api/v1/professionals/admin/profiles/{self.profile.pk}/suspend/", {"reason": "Contrôle administratif"}, format="json")
        self.assertEqual(suspended.status_code, 200, suspended.content)
        self.profile.account.refresh_from_db()
        self.assertEqual(self.profile.account.status, "suspended")
        self.assertEqual(self.client.get("/api/v1/professionals/me/").status_code, 403)

        reactivated = admin_client.post(f"/api/v1/professionals/admin/profiles/{self.profile.pk}/reactivate/", {"reason": "Contrôle terminé"}, format="json")
        self.assertEqual(reactivated.status_code, 200, reactivated.content)
        self.profile.account.refresh_from_db()
        self.assertEqual(self.profile.account.status, "active")
        self.assertTrue(AuditEvent.objects.filter(action="professional_account.suspended").exists())
        self.assertTrue(AuditEvent.objects.filter(action="professional_account.reactivated").exists())

    def test_post_review_profile_changes_require_reverification(self):
        complete = self.complete_profile()
        self.assertEqual(complete.status_code, 200)
        uploaded = self.upload_document()
        self.assertEqual(uploaded.status_code, 201)
        self.submit_profile()
        self.profile.refresh_from_db()
        admin_user = User.objects.create_superuser(username="approver", email="approver@example.test", password="R3ally-Strong-Professional-Password!")
        admin_client = APIClient(); admin_client.force_authenticate(admin_user)
        admin_client.post(f"/api/v1/admin/professional-verifications/{self.profile.verification_request_id}/review/", {"status": "approved"}, format="json")
        changed = self.patch_profile({"description": "Informations mises à jour"})
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["verification_status"], "draft")
        self.assertFalse(self.profile.account.user.groups.filter(name="professional_verified").exists())
