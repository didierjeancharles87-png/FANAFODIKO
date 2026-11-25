from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import AccountProfile

from .models import Notification, NotificationPreference, NotificationType

User = get_user_model()


class Phase7NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="phase7-notified",
            email="phase7-notified@example.test",
            password="Valid-Phase7-Password-937!",
        )
        self.account, _ = AccountProfile.objects.get_or_create(user=self.user)

    def test_whatsapp_opt_in_defaults_to_false(self):
        preference = NotificationPreference.objects.create(account=self.account)
        self.assertFalse(preference.whatsapp_opt_in)
        self.assertIsNone(preference.consent_at)

    def test_notification_starts_unread_without_whatsapp_link(self):
        notification = Notification.objects.create(
            recipient=self.account,
            notification_type=NotificationType.ORDER_CREATED,
            title="Réservation créée",
            body="Votre réservation a été enregistrée.",
        )
        self.assertIsNone(notification.read_at)
        self.assertEqual(notification.whatsapp_link, "")
        self.assertEqual(notification.link, "")
        self.assertEqual(notification.target_type, "")
        self.assertEqual(notification.target_id, "")

    def test_notification_types_are_real_business_events_only(self):
        values = {choice[0] for choice in NotificationType.choices}
        for expected in ("order_created", "order_accepted", "order_ready", "moderation_approved", "stock_depleted"):
            self.assertIn(expected, values)
        self.assertFalse(any("payment" in value for value in values))
