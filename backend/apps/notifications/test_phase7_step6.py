from decimal import Decimal
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile
from apps.audit.models import AuditEvent
from apps.marketplace.models import CatalogProduct, CatalogSeller, SellerOwner
from apps.orders.services import add_cart_item
from apps.reference.models import Country
from apps.sitecontent.models import SiteConfiguration

from .models import Notification, NotificationType
from .services import create_notification

User = get_user_model()


class Phase7NotificationTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        Group.objects.get_or_create(name="patient")
        Group.objects.get_or_create(name="professional_verified")
        self.admin = User.objects.create_superuser(
            username="notify-admin",
            email="notify-admin@example.test",
            password="Valid-Notify-Password-934!",
        )
        self.patient, self.patient_account = self.create_account("notify-patient", patient=True)
        self.partner, self.partner_account = self.create_account("notify-partner")
        self.other_patient, self.other_account = self.create_account("notify-other", patient=True)
        self.seller = CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name="Vendeur notifications",
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
            verification_reference="REF-NOTIFY",
        )
        SellerOwner.objects.create(account=self.partner_account, seller=self.seller)
        self.patient_client = self.client_for(self.patient)
        self.partner_client = self.client_for(self.partner)
        self.admin_client = self.client_for(self.admin)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create_account(self, username, patient=False):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Valid-Notify-Password-934!",
        )
        if patient:
            user.groups.add(Group.objects.get(name="patient"))
        account, _ = AccountProfile.objects.get_or_create(user=user)
        return user, account

    def configure_whatsapp(self, number="+261341234567"):
        configuration = SiteConfiguration.objects.filter(pk=1).first() or SiteConfiguration(pk=1)
        configuration.whatsapp_number = number
        configuration.updated_by = self.admin
        configuration.save()
        return configuration

    def create_product(self, stock=5, title="Matériel notifications", client=None):
        response = (client or self.partner_client).post(
            "/api/v1/partner/products/",
            {
                "product_type": "equipment",
                "title": title,
                "price_mga": "10000.00",
                "availability": "available",
                "stock_quantity": stock,
                "equipment_category": "diagnostic",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return CatalogProduct.objects.get(pk=response.json()["id"])

    def publish(self, product):
        self.assertEqual(
            self.partner_client.post(f"/api/v1/partner/products/{product.pk}/submit/", {}, format="json").status_code,
            200,
        )
        response = self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product.pk}/approve/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def checkout(self):
        response = self.patient_client.post("/api/v1/orders/", {}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()[0]

    def test_preference_defaults_to_false_and_consent_is_explicit_and_audited(self):
        response = self.patient_client.get("/api/v1/notifications/preferences/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["whatsapp_opt_in"])
        self.assertIsNone(response.json()["consent_at"])

        enabled = self.patient_client.patch(
            "/api/v1/notifications/preferences/", {"whatsapp_opt_in": True}, format="json"
        )
        self.assertEqual(enabled.status_code, 200, enabled.content)
        self.assertTrue(enabled.json()["whatsapp_opt_in"])
        self.assertIsNotNone(enabled.json()["consent_at"])
        self.assertTrue(
            AuditEvent.objects.filter(
                action="notifications.whatsapp_consent.changed", target_id=str(self.patient_account.notification_preference.pk)
            ).exists()
        )

        revoked = self.patient_client.patch(
            "/api/v1/notifications/preferences/", {"whatsapp_opt_in": False}, format="json"
        )
        self.assertEqual(revoked.status_code, 200, revoked.content)
        self.assertFalse(revoked.json()["whatsapp_opt_in"])
        self.assertIsNone(revoked.json()["consent_at"])

    def test_whatsapp_link_requires_consent_and_valid_configuration(self):
        self.configure_whatsapp("+261 34 123 456 7")
        notification = create_notification(
            recipient=self.patient_account,
            notification_type=NotificationType.ORDER_CREATED,
            title="Réservation créée",
            body="Votre réservation FMD-TEST a été créée.",
            whatsapp_message="FANAFODIKO — Réservation FMD-TEST créée.",
            target_type="orders.order",
            target_id="42",
        )
        self.assertEqual(notification.whatsapp_link, "")

        self.patient_client.patch(
            "/api/v1/notifications/preferences/", {"whatsapp_opt_in": True}, format="json"
        )
        consented = create_notification(
            recipient=self.patient_account,
            notification_type=NotificationType.ORDER_CREATED,
            title="Réservation créée",
            body="Votre réservation FMD-TEST2 a été créée.",
            whatsapp_message="FANAFODIKO — Réservation FMD-TEST2 créée.",
            target_type="orders.order",
            target_id="43",
        )
        self.assertTrue(consented.whatsapp_link.startswith("https://wa.me/261341234567?text="))
        self.assertIn("FMD-TEST2", unquote(consented.whatsapp_link))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="notifications.whatsapp_link.generated", target_id=str(consented.pk)
            ).exists()
        )

        self.configure_whatsapp("pas-un-numero")
        invalid = create_notification(
            recipient=self.patient_account,
            notification_type=NotificationType.ORDER_CREATED,
            title="Réservation créée",
            body="Votre réservation FMD-TEST3 a été créée.",
            whatsapp_message="FANAFODIKO — Réservation FMD-TEST3 créée.",
        )
        self.assertEqual(invalid.whatsapp_link, "")

    def test_revoking_consent_removes_existing_links_and_no_delivery_status_is_exposed(self):
        self.configure_whatsapp()
        self.patient_client.patch(
            "/api/v1/notifications/preferences/", {"whatsapp_opt_in": True}, format="json"
        )
        notification = create_notification(
            recipient=self.patient_account,
            notification_type=NotificationType.ORDER_READY,
            title="Réservation prête",
            body="Votre réservation FMD-READY est prête.",
            whatsapp_message="FANAFODIKO — Réservation FMD-READY prête.",
        )
        self.assertNotEqual(notification.whatsapp_link, "")

        payload = self.patient_client.get("/api/v1/notifications/").json()[0]
        self.assertEqual(payload["whatsapp_link"], notification.whatsapp_link)
        for forbidden in ("delivery_status", "read_status", "template", "sent_at", "sent"):
            self.assertNotIn(forbidden, payload)

        self.patient_client.patch(
            "/api/v1/notifications/preferences/", {"whatsapp_opt_in": False}, format="json"
        )
        notification.refresh_from_db()
        self.assertEqual(notification.whatsapp_link, "")

    def test_inbox_read_and_isolation(self):
        for index in range(3):
            create_notification(
                recipient=self.patient_account,
                notification_type=NotificationType.ORDER_CREATED,
                title=f"Notification {index}",
                body="Événement réel de test.",
            )
        other = create_notification(
            recipient=self.other_account,
            notification_type=NotificationType.ORDER_CREATED,
            title="Notification d'un autre compte",
            body="Événement réel de test.",
        )

        listing = self.patient_client.get("/api/v1/notifications/")
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(len(listing.json()), 3)
        unread = self.patient_client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(unread.json()["count"], 3)

        first_id = listing.json()[0]["id"]
        marked = self.patient_client.post(f"/api/v1/notifications/{first_id}/read/", {}, format="json")
        self.assertEqual(marked.status_code, 200, marked.content)
        self.assertIsNotNone(marked.json()["read_at"])
        self.assertEqual(self.patient_client.get("/api/v1/notifications/unread-count/").json()["count"], 2)

        read_all = self.patient_client.post("/api/v1/notifications/read-all/", {}, format="json")
        self.assertEqual(read_all.status_code, 200, read_all.content)
        self.assertEqual(read_all.json()["updated"], 2)
        self.assertEqual(self.patient_client.get("/api/v1/notifications/unread-count/").json()["count"], 0)

        self.assertEqual(
            self.patient_client.post(f"/api/v1/notifications/{other.pk}/read/", {}, format="json").status_code,
            404,
        )
        self.assertEqual(
            self.other_client().post(f"/api/v1/notifications/{first_id}/read/", {}, format="json").status_code,
            404,
        )
        self.assertEqual(self.other_client().get("/api/v1/notifications/unread-count/").json()["count"], 1)

    def other_client(self):
        return self.client_for(self.other_patient)

    def test_checkout_and_transitions_create_only_real_order_notifications(self):
        product = self.create_product(stock=4)
        self.publish(product)
        Notification.objects.all().delete()
        self.assertEqual(Notification.objects.count(), 0)
        add_cart_item(account=self.patient_account, product_id=product.pk, quantity=1)
        self.assertEqual(Notification.objects.count(), 0)

        order = self.checkout()
        self.assertEqual(
            set(Notification.objects.values_list("notification_type", flat=True)),
            {NotificationType.ORDER_CREATED},
        )
        customer_notification = Notification.objects.get(recipient=self.patient_account)
        self.assertEqual(customer_notification.target_type, "orders.order")
        self.assertEqual(customer_notification.target_id, str(order["id"]))
        self.assertEqual(customer_notification.link, f"/patient/commandes/{order['id']}")
        partner_notification = Notification.objects.get(recipient=self.partner_account)
        self.assertEqual(partner_notification.link, f"/partenaire/commandes/{order['id']}")

        self.partner_client.post(f"/api/v1/partner/orders/{order['id']}/accept/", {}, format="json")
        self.partner_client.post(f"/api/v1/partner/orders/{order['id']}/prepare/", {}, format="json")
        self.partner_client.post(f"/api/v1/partner/orders/{order['id']}/mark-ready/", {}, format="json")
        self.assertEqual(
            set(Notification.objects.filter(recipient=self.patient_account).values_list("notification_type", flat=True)),
            {
                NotificationType.ORDER_CREATED,
                NotificationType.ORDER_ACCEPTED,
                NotificationType.ORDER_PREPARING,
                NotificationType.ORDER_READY,
            },
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.partner_account).count(), 1
        )

    def test_cancellation_notifies_client_and_partner(self):
        product = self.create_product(stock=2)
        self.publish(product)
        add_cart_item(account=self.patient_account, product_id=product.pk, quantity=1)
        order = self.checkout()
        Notification.objects.all().delete()

        cancelled = self.patient_client.post(f"/api/v1/orders/{order['id']}/cancel/", {}, format="json")
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.assertEqual(
            list(Notification.objects.order_by("id").values_list("notification_type", flat=True)),
            [NotificationType.ORDER_CANCELLED, NotificationType.ORDER_CANCELLED],
        )
        self.assertTrue(
            Notification.objects.filter(recipient=self.patient_account, link=f"/patient/commandes/{order['id']}").exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.partner_account, link=f"/partenaire/commandes/{order['id']}"
            ).exists()
        )

    def test_moderation_decisions_notify_submitter(self):
        product = self.create_product(stock=1, title="Produit à modérer")
        self.assertEqual(
            self.partner_client.post(f"/api/v1/partner/products/{product.pk}/submit/", {}, format="json").status_code,
            200,
        )
        approved = self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product.pk}/approve/", {}, format="json"
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        approved_notification = Notification.objects.get(recipient=self.partner_account)
        self.assertEqual(approved_notification.notification_type, NotificationType.MODERATION_APPROVED)
        self.assertEqual(approved_notification.target_id, str(product.pk))

        product.refresh_from_db()
        self.partner_client.patch(
            f"/api/v1/partner/products/{product.pk}/", {"title": "Nouveau titre soumis"}, format="json"
        )
        rejected = self.admin_client.post(
            f"/api/v1/admin/marketplace/products/{product.pk}/reject/", {"reason": "Informations insuffisantes"}, format="json"
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)
        rejected_notification = Notification.objects.filter(
            notification_type=NotificationType.MODERATION_REJECTED
        ).get()
        self.assertEqual(rejected_notification.recipient, self.partner_account)
        self.assertIn("Informations insuffisantes", rejected_notification.body)
        self.assertNotIn("FMD", rejected_notification.whatsapp_link)

    def test_stock_depletion_notifies_partner_on_checkout_and_on_partner_edit(self):
        product = self.create_product(stock=1)
        self.publish(product)
        add_cart_item(account=self.patient_account, product_id=product.pk, quantity=1)
        self.checkout()
        depleted = Notification.objects.filter(notification_type=NotificationType.STOCK_DEPLETED)
        self.assertEqual(depleted.count(), 1)
        self.assertEqual(depleted.get().recipient, self.partner_account)
        self.assertEqual(depleted.get().link, f"/partenaire/produits/{product.pk}")

        refreshed = self.create_product(stock=2, title="Deuxième matériel")
        patch = self.partner_client.patch(
            f"/api/v1/partner/products/{refreshed.pk}/", {"stock_quantity": 0}, format="json"
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        self.assertEqual(
            Notification.objects.filter(notification_type=NotificationType.STOCK_DEPLETED).count(), 2
        )
