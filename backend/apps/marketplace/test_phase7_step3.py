from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country

from .models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory, SellerOwner

User = get_user_model()
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def png_upload(name="gallery.png", content_type="image/png", size=None):
    data = PNG_BYTES if size is None else PNG_BYTES + b"\x00" * size
    return SimpleUploadedFile(name, data, content_type=content_type)


class Phase7Step3Tests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="step3-admin", email="step3-admin@example.test", password="Valid-Step3-Password-934!"
        )
        self.admin_client = self.client_for(self.admin)
        self.public_client = APIClient()

        self.seller_a = self.create_supplier("Vendeur Step3 A", "REF-STEP3-A")
        self.seller_b = self.create_supplier("Vendeur Step3 B", "REF-STEP3-B")
        self.user_a, self.account_a = self.create_account("step3-partner-a")
        self.user_b, self.account_b = self.create_account("step3-partner-b")
        SellerOwner.objects.create(account=self.account_a, seller=self.seller_a)
        SellerOwner.objects.create(account=self.account_b, seller=self.seller_b)
        self.client_a = self.client_for(self.user_a)
        self.client_b = self.client_for(self.user_b)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_account(self, username, status=AccountProfile.Status.ACTIVE):
        user = User.objects.create_user(username=username, email=f"{username}@example.test", password="Valid-Step3-Password-934!")
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

    def equipment_payload(self, **overrides):
        payload = {
            "product_type": "equipment",
            "title": "Appareil de diagnostic Step3",
            "brand": "Marque test",
            "description": "Description de test",
            "price_mga": "15000.00",
            "availability": "available",
            "stock_quantity": 5,
            "equipment_category": "diagnostic",
            "technical_specifications": {"usage": "test"},
        }
        payload.update(overrides)
        return payload

    def create_product_api(self, **overrides):
        return self.client_a.post("/api/v1/partner/products/", self.equipment_payload(**overrides), format="json")

    def submit(self, product, client=None):
        return (client or self.client_a).post(f"/api/v1/partner/products/{product.pk}/submit/", {}, format="json")

    def approve(self, product, client=None):
        return (client or self.admin_client).post(f"/api/v1/admin/marketplace/products/{product.pk}/approve/", {}, format="json")

    def reject(self, product, reason="Non conforme", client=None):
        return (client or self.admin_client).post(
            f"/api/v1/admin/marketplace/products/{product.pk}/reject/", {"reason": reason}, format="json"
        )

    def create_verified_pharmacy_owner(self, username):
        user, account = self.create_account(username)
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

    def test_partner_creates_draft_with_forced_seller_and_initial_price_history(self):
        response = self.create_product_api(seller=self.seller_b.pk, status="published", moderation_status="approved")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["seller"], self.seller_a.pk)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["moderation_status"], "not_required")

        product = CatalogProduct.objects.get(pk=data["id"])
        self.assertEqual(product.created_by, self.user_a)
        history = ProductPriceHistory.objects.filter(product=product)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().price_mga, Decimal("15000.00"))
        self.assertEqual(history.first().reason, "Prix initial")
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.created", target_id=str(product.pk)).exists())

    def test_invalid_price_is_rejected_without_price_history(self):
        response = self.create_product_api(price_mga="0")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(ProductPriceHistory.objects.count(), 0)
        self.assertEqual(CatalogProduct.objects.count(), 0)

    def test_stock_null_and_zero_are_accepted_but_timestamps_track_real_changes(self):
        response = self.create_product_api(stock_quantity=None)
        self.assertEqual(response.status_code, 201, response.content)
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.assertIsNone(product.stock_quantity)

        null_change = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"stock_quantity": None}, format="json"
        )
        self.assertEqual(null_change.status_code, 200, null_change.content)
        self.assertIsNone(null_change.json()["stock_updated_at"])

        zero_change = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"stock_quantity": 0}, format="json"
        )
        self.assertEqual(zero_change.status_code, 200, zero_change.content)
        self.assertIsNotNone(zero_change.json()["stock_updated_at"])
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)

    def test_price_history_records_only_real_changes(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])

        no_change = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"price_mga": "15000.00"}, format="json"
        )
        self.assertEqual(no_change.status_code, 200, no_change.content)
        self.assertEqual(ProductPriceHistory.objects.filter(product=product).count(), 1)

        changed = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"price_mga": "18000.00"}, format="json"
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(ProductPriceHistory.objects.filter(product=product).count(), 2)
        latest = ProductPriceHistory.objects.filter(product=product).order_by("-changed_at").first()
        self.assertEqual(latest.price_mga, Decimal("18000.00"))
        self.assertEqual(latest.changed_by, self.user_a)

    def test_moderation_approve_publishes_and_audits(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])

        submit_response = self.submit(product)
        self.assertEqual(submit_response.status_code, 200, submit_response.content)
        product.refresh_from_db()
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.PENDING)
        self.assertIsNotNone(product.submitted_for_review_at)
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.submitted", target_id=str(product.pk)).exists())

        approve_response = self.approve(product)
        self.assertEqual(approve_response.status_code, 200, approve_response.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.PUBLISHED)
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.APPROVED)
        self.assertEqual(product.reviewed_by, self.admin)
        self.assertIsNotNone(product.reviewed_at)
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.approved", target_id=str(product.pk)).exists())

        public_response = self.public_client.get(f"/api/v1/marketplace/public/products/{product.slug}/")
        self.assertEqual(public_response.status_code, 200, public_response.content)

    def test_moderation_reject_requires_reason_and_audits(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.submit(product)

        missing_reason = self.reject(product, reason="")
        self.assertEqual(missing_reason.status_code, 400, missing_reason.content)

        reject_response = self.reject(product, reason="Informations insuffisantes")
        self.assertEqual(reject_response.status_code, 200, reject_response.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.DRAFT)
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.REJECTED)
        self.assertEqual(product.review_notes, "Informations insuffisantes")
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.rejected", target_id=str(product.pk)).exists())

    def test_substantive_edit_after_approval_requires_new_moderation(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.submit(product)
        self.approve(product)

        edit = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"title": "Titre modifié après approbation"}, format="json"
        )
        self.assertEqual(edit.status_code, 200, edit.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.DRAFT)
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.PENDING)
        self.assertIsNone(product.reviewed_by)
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.resubmitted", target_id=str(product.pk)).exists())

    def test_non_substantive_stock_edit_does_not_reset_approval(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.submit(product)
        self.approve(product)

        edit = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"stock_quantity": 2}, format="json"
        )
        self.assertEqual(edit.status_code, 200, edit.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.PUBLISHED)
        self.assertEqual(product.moderation_status, CatalogProduct.ModerationStatus.APPROVED)

    def test_archive_is_logical_and_archived_product_cannot_be_edited(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])

        delete_response = self.client_a.delete(f"/api/v1/partner/products/{product.pk}/")
        self.assertEqual(delete_response.status_code, 204, delete_response.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.ARCHIVED)
        self.assertTrue(CatalogProduct.objects.filter(pk=product.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="marketplace.product.archived", target_id=str(product.pk)).exists())

        patch_response = self.client_a.patch(
            f"/api/v1/partner/products/{product.pk}/", {"title": "Interdit"}, format="json"
        )
        self.assertEqual(patch_response.status_code, 400, patch_response.content)

    def test_isolation_applies_to_create_submit_moderation_and_gallery(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])

        own_submit = self.submit(product)
        self.assertEqual(own_submit.status_code, 200, own_submit.content)

        for method, path, data in (
            ("get", f"/api/v1/partner/products/{product.pk}/", None),
            ("patch", f"/api/v1/partner/products/{product.pk}/", {"title": "Intrusion"}),
            ("delete", f"/api/v1/partner/products/{product.pk}/", None),
            ("post", f"/api/v1/partner/products/{product.pk}/submit/", {}),
            ("get", f"/api/v1/partner/products/{product.pk}/images/", None),
        ):
            if method == "patch":
                response = self.client_b.patch(path, data, format="json")
            elif method == "post":
                response = self.client_b.post(path, data, format="json")
            elif method == "delete":
                response = self.client_b.delete(path)
            else:
                response = self.client_b.get(path)
            self.assertEqual(response.status_code, 404, (method, path, response.content))

        other_create = self.client_b.post(
            "/api/v1/partner/products/", self.equipment_payload(title="Produit partenaire B"), format="json"
        )
        self.assertEqual(other_create.status_code, 201, other_create.content)
        self.assertEqual(other_create.json()["seller"], self.seller_b.pk)

    def test_gallery_uploads_private_images_and_primary_image(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])

        first = self.client_a.post(
            f"/api/v1/partner/products/{product.pk}/images/",
            {"file": png_upload("premiere.png"), "alt_text": "Vue de face", "sort_order": 1},
            format="multipart",
        )
        self.assertEqual(first.status_code, 201, first.content)
        first_data = first.json()
        self.assertNotIn("private_media", first_data["file_url"])
        self.assertTrue(first_data["is_primary"])

        second = self.client_a.post(
            f"/api/v1/partner/products/{product.pk}/images/",
            {"file": png_upload("deuxieme.png"), "alt_text": "Vue de dos", "sort_order": 2},
            format="multipart",
        )
        self.assertEqual(second.status_code, 201, second.content)
        self.assertFalse(second.json()["is_primary"])

        image = ProductImage.objects.get(pk=second.json()["id"])
        primary = self.client_a.post(f"/api/v1/partner/products/{product.pk}/images/{image.pk}/primary/", {}, format="json")
        self.assertEqual(primary.status_code, 200, primary.content)
        product.refresh_from_db()
        self.assertEqual(product.image.name, image.file.name)

        file_response = self.client_a.get(f"/api/v1/partner/products/{product.pk}/images/{image.pk}/file/")
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(b"".join(file_response.streaming_content), PNG_BYTES)
        self.assertEqual(file_response["Content-Type"], "image/png")
        self.assertEqual(file_response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(file_response["Cache-Control"], "private, no-store")

        forbidden = self.client_b.get(f"/api/v1/partner/products/{product.pk}/images/{image.pk}/file/")
        self.assertEqual(forbidden.status_code, 404, forbidden.content)

    def test_gallery_rejects_invalid_extension_mime_signature_and_size(self):
        response = self.create_product_api()
        product_id = response.json()["id"]
        url = f"/api/v1/partner/products/{product_id}/images/"

        cases = (
            {"file": SimpleUploadedFile("image.gif", PNG_BYTES, content_type="image/gif")},
            {"file": SimpleUploadedFile("image.png", PNG_BYTES, content_type="image/jpeg")},
            {"file": SimpleUploadedFile("image.png", b"not-an-image", content_type="image/png")},
            {"file": png_upload(size=2 * 1024 * 1024)},
        )
        for payload in cases:
            invalid = self.client_a.post(url, payload, format="multipart")
            self.assertEqual(invalid.status_code, 400, invalid.content)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_deleting_primary_image_promotes_another_image(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        first = self.client_a.post(
            f"/api/v1/partner/products/{product.pk}/images/",
            {"file": png_upload("a.png"), "sort_order": 1},
            format="multipart",
        )
        second = self.client_a.post(
            f"/api/v1/partner/products/{product.pk}/images/",
            {"file": png_upload("b.png"), "sort_order": 2},
            format="multipart",
        )
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)

        delete_response = self.client_a.delete(f"/api/v1/partner/products/{product.pk}/images/{first.json()['id']}/")
        self.assertEqual(delete_response.status_code, 204, delete_response.content)

        product.refresh_from_db()
        remaining = ProductImage.objects.get(product=product)
        self.assertTrue(remaining.is_primary)
        self.assertEqual(product.image.name, remaining.file.name)

    def test_medicine_approval_requires_verified_amm(self):
        user, _, seller = self.create_verified_pharmacy_owner("step3-pharmacy-owner")
        client = self.client_for(user)
        create_response = client.post(
            "/api/v1/partner/products/",
            {
                "product_type": "medicine",
                "title": "Médicament Step3",
                "price_mga": "5000.00",
                "availability": "available",
                "stock_quantity": 10,
                "active_ingredient": "Paracétamol",
                "dosage": "500 mg",
                "pharmaceutical_form": "Comprimé",
                "packaging": "Boîte de 20",
                "requires_prescription": True,
                "authorization_status": "pending",
                "authorization_reference": "",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)
        product = CatalogProduct.objects.get(pk=create_response.json()["id"])
        self.assertEqual(self.submit(product, client=client).status_code, 200)

        denied = self.approve(product)
        self.assertEqual(denied.status_code, 400, denied.content)

        declared = client.patch(
            f"/api/v1/partner/products/{product.pk}/",
            {"authorization_status": "verified", "authorization_reference": "AMM-STEP3-001"},
            format="json",
        )
        self.assertEqual(declared.status_code, 200, declared.content)
        product.refresh_from_db()
        self.assertEqual(product.authorization_status, CatalogProduct.AuthorizationStatus.PENDING)

        verified = self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product.pk}/authorization/verify/", {}, format="json"
        )
        self.assertEqual(verified.status_code, 200, verified.content)
        self.submit(product, client=client)
        approved = self.approve(product)
        self.assertEqual(approved.status_code, 200, approved.content)
        product.refresh_from_db()
        self.assertEqual(product.status, CatalogProduct.Status.PUBLISHED)

    def test_admin_moderation_queue_and_price_history(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.submit(product)

        queue = self.admin_client.get("/api/v1/admin/marketplace/moderation/products/")
        self.assertEqual(queue.status_code, 200, queue.content)
        ids = {item["id"] for item in queue.json()["results"]}
        self.assertIn(product.pk, ids)

        self.client_a.patch(f"/api/v1/partner/products/{product.pk}/", {"price_mga": "20000.00"}, format="json")
        history = self.admin_client.get(f"/api/v1/admin/marketplace/products/{product.pk}/price-history/")
        self.assertEqual(history.status_code, 200, history.content)
        self.assertEqual(history.json()["results"][0]["price_mga"], "20000.00")

    def test_public_catalog_exposes_gallery_file_urls(self):
        response = self.create_product_api()
        product = CatalogProduct.objects.get(pk=response.json()["id"])
        self.submit(product)
        self.approve(product)
        upload = self.client_a.post(
            f"/api/v1/partner/products/{product.pk}/images/",
            {"file": png_upload("public.png"), "alt_text": "Vue publique"},
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201, upload.content)

        detail = self.public_client.get(f"/api/v1/marketplace/public/products/{product.slug}/")
        self.assertEqual(detail.status_code, 200, detail.content)
        images = detail.json()["images"]
        self.assertEqual(len(images), 1)
        self.assertIn(f"/public/products/{product.slug}/images/{upload.json()['id']}/", images[0]["url"])

        image_response = self.public_client.get(images[0]["url"].replace("http://testserver", ""))
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(b"".join(image_response.streaming_content), PNG_BYTES)
        self.assertEqual(image_response["Cache-Control"], "public, max-age=300")
