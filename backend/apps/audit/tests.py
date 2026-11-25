from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.reference.models import Country

from .models import AuditEvent
from .services import record_event


class AuditEventTests(TestCase):
    def test_action_is_recorded_with_actor_target_and_client_address(self):
        actor = get_user_model().objects.create_user(username="auditor", password="Safe-test-password-928")
        country = Country.objects.get(code_alpha2="MG")
        request = RequestFactory().post("/admin/reference/country/")
        request.META["REMOTE_ADDR"] = "192.0.2.20"

        event = record_event(actor=actor, action="reference.country.updated", target=country, request=request)

        self.assertEqual(event.actor, actor)
        self.assertEqual(event.target_type, "reference.country")
        self.assertEqual(event.target_id, str(country.pk))
        self.assertEqual(event.remote_addr, "192.0.2.20")

    def test_audit_records_are_read_only_in_django_admin(self):
        event_admin = admin.site._registry[AuditEvent]

        self.assertFalse(event_admin.has_add_permission(None))
        self.assertTrue(event_admin.has_change_permission(None))
        self.assertFalse(event_admin.has_delete_permission(None))
