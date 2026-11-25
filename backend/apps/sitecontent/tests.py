from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from .models import FAQEntry, NewsArticle, PageContent, SiteConfiguration, SiteImage


User = get_user_model()


def grant_permission(user, label):
    app_label, codename = label.split(".", 1)
    user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return User.objects.get(pk=user.pk)


class SiteContentAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="site-admin", email="site-admin@example.test", password="Strong-admin-password-928!")
        self.staff = User.objects.create_user(username="site-staff", email="site-staff@example.test", password="Strong-staff-password-928!", is_staff=True)
        for label in (
            "sitecontent.change_siteconfiguration",
            "sitecontent.add_faqentry",
            "sitecontent.change_faqentry",
            "sitecontent.add_newsarticle",
            "sitecontent.change_newsarticle",
            "sitecontent.add_pagecontent",
        ):
            self.staff = grant_permission(self.staff, label)
        self.client = APIClient()

    def test_only_active_staff_can_edit_site_configuration_and_public_value_is_read_only(self):
        denied = self.client.patch("/api/v1/site-content/admin/configuration/", {"whatsapp_number": "+261 38 16 27 248"}, format="json")
        self.assertEqual(denied.status_code, 403)
        regular_user = User.objects.create_user(username="site-reader", email="site-reader@example.test", password="Strong-reader-password-928!")
        self.client.force_authenticate(regular_user)
        forbidden = self.client.get("/api/v1/site-content/admin/faqs/")
        self.assertEqual(forbidden.status_code, 403)
        self.client.force_authenticate(self.staff)
        response = self.client.patch("/api/v1/site-content/admin/configuration/", {"whatsapp_number": "+261 38 16 27 248"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(SiteConfiguration.objects.get().whatsapp_number, "+261381627248")
        invalid = self.client.patch("/api/v1/site-content/admin/configuration/", {"whatsapp_number": "not-a-number"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        public = APIClient().get("/api/v1/site-content/public/configuration/")
        self.assertEqual(public.json()["whatsapp_number"], "+261381627248")
        self.assertTrue(AuditEvent.objects.filter(action="site_content.configuration.updated", actor=self.staff).exists())

    def test_faq_news_and_page_permissions_and_public_visibility(self):
        self.client.force_authenticate(self.staff)
        faq = self.client.post("/api/v1/site-content/admin/faqs/", {"question": "Question réelle ?", "answer": "Réponse vérifiée", "sort_order": 2, "is_visible": True}, format="json")
        self.assertEqual(faq.status_code, 201, faq.content)
        article = self.client.post("/api/v1/site-content/admin/news/", {"title": "Annonce test", "summary": "Résumé", "body": "Texte", "is_published": False}, format="json")
        self.assertEqual(article.status_code, 201, article.content)
        self.assertEqual(APIClient().get("/api/v1/site-content/public/news/").json(), [])
        article = self.client.patch(f"/api/v1/site-content/admin/news/{article.json()['id']}/", {"is_published": True}, format="json")
        self.assertEqual(article.status_code, 200)
        self.assertEqual(len(APIClient().get("/api/v1/site-content/public/news/").json()), 1)
        hidden = self.client.patch(f"/api/v1/site-content/admin/faqs/{faq.json()['id']}/", {"is_visible": False}, format="json")
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(APIClient().get("/api/v1/site-content/public/faqs/").json()["entries"], [])
        page = self.client.post("/api/v1/site-content/admin/pages/", {"page": "about", "title": "À propos", "introduction": "Texte éditorial", "body": "Contenu"}, format="json")
        self.assertEqual(page.status_code, 201, page.content)
        self.assertEqual(APIClient().get("/api/v1/site-content/public/pages/about/").json()["title"], "À propos")
        self.assertTrue(AuditEvent.objects.filter(action="site_content.faq.created", actor=self.staff).exists())

    def test_image_upload_replace_public_read_and_delete_never_reads_private_documents(self):
        self.client.force_authenticate(self.admin)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 12
        uploaded = SimpleUploadedFile("hero.png", png, content_type="image/png")
        response = self.client.post("/api/v1/site-content/admin/images/", {"slot": "teleconsultation", "image": uploaded, "alt_text": "Illustration médicale"}, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        asset_id = response.json()["id"]
        public = APIClient().get("/api/v1/site-content/public/images/teleconsultation/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public["Content-Type"], "image/png")
        self.assertEqual(b"".join(public.streaming_content), png)
        replacement = SimpleUploadedFile("hero-new.png", png + b"replacement", content_type="image/png")
        replaced = self.client.post("/api/v1/site-content/admin/images/", {"slot": "teleconsultation", "image": replacement, "alt_text": "Nouvelle illustration"}, format="multipart")
        self.assertEqual(replaced.status_code, 201, replaced.content)
        self.assertEqual(SiteImage.objects.count(), 1)
        deleted = self.client.delete(f"/api/v1/site-content/admin/images/{asset_id}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(SiteImage.objects.count(), 1)
        self.assertFalse(SiteImage.objects.get().is_visible)
        self.assertEqual(APIClient().get("/api/v1/site-content/public/images/").json()["hidden_slots"], ["teleconsultation"])
        self.assertEqual(APIClient().get("/api/v1/site-content/public/images/teleconsultation/").status_code, 404)

        restored = SimpleUploadedFile("hero-restored.png", png, content_type="image/png")
        reactivated = self.client.post("/api/v1/site-content/admin/images/", {"slot": "teleconsultation", "image": restored, "alt_text": "Image restaurée"}, format="multipart")
        self.assertEqual(reactivated.status_code, 201, reactivated.content)
        self.assertTrue(SiteImage.objects.get().is_visible)

        invalid = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        rejected = self.client.post("/api/v1/site-content/admin/images/", {"slot": "pharmacy", "image": invalid, "alt_text": "Pas une image"}, format="multipart")
        self.assertEqual(rejected.status_code, 400)
        self.assertTrue(AuditEvent.objects.filter(action="site_content.image.deleted", actor=self.admin).exists())

