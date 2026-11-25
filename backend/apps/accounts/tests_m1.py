from datetime import timedelta

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AccountProfile
from .services import LOGOUT_ONLY_SESSION_KEY

User = get_user_model()


class SuspendedSessionRevocationTests(TestCase):
    def login_client(self, username):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        response = client.post(
            "/api/v1/auth/login/",
            {"email": f"{username}@example.test", "password": "Strong-Session-Password-928!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return client, client.cookies["csrftoken"].value

    def create_user(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Strong-Session-Password-928!",
        )

    def test_suspension_revokes_session_but_keeps_logout_with_csrf(self):
        user = self.create_user("suspended-session")
        client, csrf = self.login_client("suspended-session")
        session_key = client.session.session_key
        self.assertIsNotNone(session_key)

        user.account_profile.status = AccountProfile.Status.SUSPENDED
        user.account_profile.save(update_fields=("status", "updated_at"))

        session = Session.objects.get(pk=session_key)
        data = session.get_decoded()
        self.assertNotIn(SESSION_KEY, data)
        self.assertEqual(data[LOGOUT_ONLY_SESSION_KEY], user.pk)

        self.assertIn(client.get("/api/v1/auth/me/").status_code, (401, 403))
        self.assertEqual(client.post("/api/v1/auth/logout/").status_code, 403)
        self.assertEqual(client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf).status_code, 204)
        self.assertFalse(Session.objects.filter(pk=session_key).exists())

    def test_logout_only_session_cannot_reach_other_authenticated_apis(self):
        user = self.create_user("logout-only-session")
        client, _csrf = self.login_client("logout-only-session")

        user.account_profile.status = AccountProfile.Status.SUSPENDED
        user.account_profile.save(update_fields=("status", "updated_at"))

        for path in (
            "/api/v1/auth/me/",
            "/api/v1/accounts/professional-verifications/",
            "/api/v1/professionals/me/",
        ):
            with self.subTest(path=path):
                self.assertIn(client.get(path).status_code, (401, 403))

    def test_suspension_does_not_touch_another_users_session(self):
        suspended = self.create_user("suspended-other")
        other = self.create_user("other-active")
        suspended_client, _csrf = self.login_client("suspended-other")
        other_client, _other_csrf = self.login_client("other-active")
        other_session_key = other_client.session.session_key

        suspended.account_profile.status = AccountProfile.Status.SUSPENDED
        suspended.account_profile.save(update_fields=("status", "updated_at"))

        self.assertIn(suspended_client.get("/api/v1/auth/me/").status_code, (401, 403))
        self.assertEqual(other_client.get("/api/v1/auth/me/").status_code, 200)
        self.assertIn(SESSION_KEY, Session.objects.get(pk=other_session_key).get_decoded())

    def test_expired_session_is_not_revived_by_suspension(self):
        user = self.create_user("expired-session")
        expired = Session.objects.create(
            session_key="expired-session-key",
            session_data=SessionStore().encode({SESSION_KEY: str(user.pk)}),
            expire_date=timezone.now() - timedelta(days=1),
        )

        user.account_profile.status = AccountProfile.Status.SUSPENDED
        user.account_profile.save(update_fields=("status", "updated_at"))

        expired.refresh_from_db()
        self.assertLess(expired.expire_date, timezone.now())
        self.assertEqual(expired.get_decoded()[SESSION_KEY], str(user.pk))
        self.assertNotIn(LOGOUT_ONLY_SESSION_KEY, expired.get_decoded())

    def test_reactivation_does_not_restore_old_session(self):
        user = self.create_user("reactivated-session")
        client, csrf = self.login_client("reactivated-session")
        session_key = client.session.session_key

        profile = user.account_profile
        profile.status = AccountProfile.Status.SUSPENDED
        profile.save(update_fields=("status", "updated_at"))
        profile.status = AccountProfile.Status.ACTIVE
        profile.save(update_fields=("status", "updated_at"))

        self.assertNotIn(SESSION_KEY, Session.objects.get(pk=session_key).get_decoded())
        self.assertIn(client.get("/api/v1/auth/me/").status_code, (401, 403))
        self.assertIn(client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf).status_code, (401, 403))

        new_client, new_csrf = self.login_client("reactivated-session")
        self.assertEqual(new_client.get("/api/v1/auth/me/").status_code, 200)
        self.assertNotEqual(new_client.session.session_key, session_key)
        self.assertEqual(new_client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=new_csrf).status_code, 204)

    def test_user_deactivation_revokes_session_and_allows_logout(self):
        user = self.create_user("disabled-session")
        client, csrf = self.login_client("disabled-session")
        session_key = client.session.session_key

        user.is_active = False
        user.save(update_fields=("is_active",))

        self.assertNotIn(SESSION_KEY, Session.objects.get(pk=session_key).get_decoded())
        self.assertIn(client.get("/api/v1/auth/me/").status_code, (401, 403))
        logout = client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(logout.status_code, 204, logout.content)
