"""Limitation de débit configurable, par adresse IP et par compte.

Les clés de cache sont hachées : aucune adresse e-mail n'est stockée en clair
dans le cache. Les portées restent indépendantes pour ne pas bloquer un
utilisateur légitime sur une autre fonctionnalité.
"""

import hashlib

from rest_framework.exceptions import Throttled
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


class ConfigurableThrottled(Throttled):
    """Erreur 429 en français, sans duplication du délai d’attente."""

    default_detail = "Trop de tentatives."
    extra_detail_singular = "Réessayez dans {wait} seconde."
    extra_detail_plural = "Réessayez dans {wait} secondes."


class ConfigurableRateThrottle(SimpleRateThrottle):
    """Lit la limite depuis les réglages au moment de la requête.

    DRF capture normalement ``DEFAULT_THROTTLE_RATES`` à l'import, ce qui
    empêcherait les tests de remplacer une limite avec ``override_settings``.
    """

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    @staticmethod
    def hash_identity(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:40]

    def throttle_failure(self):
        wait = self.wait()
        # ``wait`` peut être None si l’historique contient déjà plus de
        # requêtes que la limite : DRF ne doit pas comparer None à un entier.
        if wait is None:
            raise ConfigurableThrottled()
        raise ConfigurableThrottled(wait=wait)


class IPRateThrottle(ConfigurableRateThrottle):
    def get_cache_key(self, request, view):
        ident = self.get_ident(request) or "unknown"
        return self.hash_identity(f"ip:{ident}")


class AccountRateThrottle(ConfigurableRateThrottle):
    """Identifiant stable : compte authentifié, sinon adresse e-mail soumise.

    Une adresse e-mail frauduleuse ne peut pénaliser que la requête depuis la
    même IP ; la limite IP indépendante empêche la saturation par rotation
    d'adresses e-mail.
    """

    email_field = "email"

    def account_identity(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return f"user:{user.pk}"
        data = getattr(request, "data", None) or {}
        email = data.get(self.email_field)
        if email:
            return f"email:{str(email).strip().lower()}"
        params = getattr(request, "query_params", None) or {}
        email = params.get(self.email_field)
        if email:
            return f"email:{str(email).strip().lower()}"
        return None

    def get_cache_key(self, request, view):
        identity = self.account_identity(request)
        if not identity:
            return None
        return self.hash_identity(f"account:{self.scope}:{identity}")


class LoginIPRateThrottle(IPRateThrottle):
    scope = "login_ip"


class LoginAccountRateThrottle(AccountRateThrottle):
    scope = "login_account"


class RegistrationIPRateThrottle(IPRateThrottle):
    scope = "register_ip"


class RegistrationAccountRateThrottle(AccountRateThrottle):
    scope = "register_account"


class CsrfIPRateThrottle(IPRateThrottle):
    scope = "csrf_ip"


class CouponIPRateThrottle(IPRateThrottle):
    scope = "coupon_ip"


class CouponAccountRateThrottle(AccountRateThrottle):
    scope = "coupon_account"
