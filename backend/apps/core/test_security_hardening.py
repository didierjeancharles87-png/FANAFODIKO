"""Tests de non-régression E1 (configuration production) et E2 (débits)."""

import importlib
import os
import sys
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AccountProfile


PRODUCTION_MODULE = "config.settings.production"
VALID_SECRET = "ProductionOnlySecret-" + "a" * 48


def load_production_module():
    """Recharge le module avec un environnement contrôlé, sans toucher aux réglages actifs."""
    with mock.patch.dict(
        os.environ,
        {
            "DJANGO_SECRET_KEY": VALID_SECRET,
            "DJANGO_ALLOWED_HOSTS": "api.fanafodiko.test",
            "DJANGO_DEBUG": "True",
        },
    ):
        sys.modules.pop(PRODUCTION_MODULE, None)
        return importlib.import_module(PRODUCTION_MODULE)


def rate_settings(**overrides):
    rates = {scope: "100000/d" for scope in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]}
    rates.update(overrides)
    return {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}


class ProductionSecurityTests(SimpleTestCase):
    def test_production_forces_debug_off_and_secure_transport(self):
        production = load_production_module()
        self.assertIs(production.DEBUG, False)
        self.assertTrue(production.SECURE_SSL_REDIRECT)
        self.assertTrue(production.SESSION_COOKIE_SECURE)
        self.assertTrue(production.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(production.CSRF_COOKIE_SECURE)
        self.assertGreaterEqual(production.SECURE_HSTS_SECONDS, 31536000)
        self.assertEqual(production.X_FRAME_OPTIONS, "DENY")

    def test_production_secret_rejects_missing_short_and_development_values(self):
        production = load_production_module()
        for candidate in ("", "   ", "too-short", "unsafe-development-key-change-me", "changeme-please-1234567890123456789"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    production.resolve_production_secret(candidate)
                if candidate.strip():
                    self.assertNotIn(candidate.strip(), str(caught.exception))
        self.assertEqual(production.resolve_production_secret(f"  {VALID_SECRET}  "), VALID_SECRET)

    def test_production_hosts_reject_empty_and_wildcard(self):
        production = load_production_module()
        for hosts in ([], ["", "  "], ["*"], ["api.example.test", "*"]):
            with self.subTest(hosts=hosts):
                with self.assertRaises(ImproperlyConfigured):
                    production.validate_production_hosts(hosts)
        self.assertEqual(
            production.validate_production_hosts([" api.example.test ", "", "www.example.test"]),
            ["api.example.test", "www.example.test"],
        )


class ThrottlingSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def assert_throttled(self, response):
        self.assertEqual(response.status_code, 429, response.content)
        body = response.json()["error"]
        self.assertEqual(body["status"], 429)
        self.assertEqual(body["code"], "throttled")
        self.assertIn("Réessayez", body["message"])
        self.assertNotIn("Expected available", body["message"])

    def login(self, email, remote_addr="10.0.0.1"):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": "Wrong-password-934!"},
            format="json",
            REMOTE_ADDR=remote_addr,
        )

    def test_login_is_limited_per_ip(self):
        with override_settings(REST_FRAMEWORK=rate_settings(login_ip="2/m")):
            first = self.login("unknown@example.test")
            second = self.login("unknown@example.test")
            third = self.login("unknown@example.test")
        self.assertIn(first.status_code, (400, 403))
        self.assertIn(second.status_code, (400, 403))
        self.assert_throttled(third)

    def test_login_is_limited_per_account_even_when_ip_changes(self):
        with override_settings(REST_FRAMEWORK=rate_settings(login_account="2/m")):
            first = self.login("cible@example.test", "10.1.0.1")
            second = self.login("cible@example.test", "10.1.0.2")
            third = self.login("cible@example.test", "10.1.0.3")
            other = self.login("autre@example.test", "10.1.0.4")
        self.assertIn(first.status_code, (400, 403))
        self.assertIn(second.status_code, (400, 403))
        self.assert_throttled(third)
        self.assertIn(other.status_code, (400, 403))

    def test_registration_is_limited_per_ip_and_per_email(self):
        with override_settings(REST_FRAMEWORK=rate_settings(register_ip="2/m")):
            first = self.client.post("/api/v1/auth/register-patient/", {}, format="json")
            second = self.client.post("/api/v1/auth/register-patient/", {}, format="json")
            third = self.client.post("/api/v1/auth/register-patient/", {}, format="json")
        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assert_throttled(third)

        cache.clear()
        with override_settings(REST_FRAMEWORK=rate_settings(register_account="2/m")):
            first = self.client.post("/api/v1/auth/register-patient/", {"email": "inscription@example.test"}, format="json", REMOTE_ADDR="10.2.0.1")
            second = self.client.post("/api/v1/auth/register-patient/", {"email": "inscription@example.test"}, format="json", REMOTE_ADDR="10.2.0.2")
            third = self.client.post("/api/v1/auth/register-patient/", {"email": "inscription@example.test"}, format="json", REMOTE_ADDR="10.2.0.3")
            other = self.client.post("/api/v1/auth/register-patient/", {"email": "autre-inscription@example.test"}, format="json", REMOTE_ADDR="10.2.0.4")
        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assert_throttled(third)
        self.assertEqual(other.status_code, 400)

    def test_csrf_cookie_endpoint_is_limited_per_ip(self):
        with override_settings(REST_FRAMEWORK=rate_settings(csrf_ip="2/m")):
            first = self.client.get("/api/v1/auth/csrf/")
            second = self.client.get("/api/v1/auth/csrf/")
            third = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assert_throttled(third)

    def test_coupon_application_is_limited_but_coupon_read_is_not(self):
        user = get_user_model().objects.create_user(
            username="coupon-throttle", email="coupon-throttle@example.test", password="Safe-password-934!"
        )
        AccountProfile.objects.get_or_create(user=user)
        user.groups.add(Group.objects.get_or_create(name="patient")[0])
        client = APIClient()
        client.force_authenticate(user)
        with override_settings(REST_FRAMEWORK=rate_settings(coupon_ip="2/m", coupon_account="2/m")):
            for _ in range(3):
                self.assertEqual(client.get("/api/v1/cart/").status_code, 200)
            first = client.post("/api/v1/cart/coupon/", {"code": "INCONNU"}, format="json")
            second = client.post("/api/v1/cart/coupon/", {"code": "INCONNU"}, format="json")
            third = client.post("/api/v1/cart/coupon/", {"code": "INCONNU"}, format="json")
        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assert_throttled(third)
