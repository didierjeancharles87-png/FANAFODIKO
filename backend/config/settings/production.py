"""Réglages strictement réservés à la production.

Ce module ne doit jamais être importé par les environnements de test ou de
développement locaux : il refuse les clés de développement et force DEBUG à
False avant toute initialisation de l'application.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env_flag, env_int

DEVELOPMENT_SECRET_MARKERS = (
    "unsafe-development-key",
    "replace-with",
    "dev-only",
    "local-only",
    "test-only",
    "insecure",
    "changeme",
)


def resolve_production_secret(raw_secret):
    """Valide la clé secrète sans jamais la journaliser ni la renvoyer telle quelle."""
    secret = (raw_secret or "").strip()
    if not secret:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
    if len(secret) < 32:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 32 characters in production.")
    normalized = secret.lower()
    if any(marker in normalized for marker in DEVELOPMENT_SECRET_MARKERS):
        raise ImproperlyConfigured("DJANGO_SECRET_KEY cannot use a development value in production.")
    return secret


def validate_production_hosts(hosts):
    allowed = [str(host).strip() for host in (hosts or []) if str(host).strip()]
    if not allowed:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
    if "*" in allowed:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS cannot contain a wildcard in production.")
    return allowed


SECRET_KEY = resolve_production_secret(os.getenv("DJANGO_SECRET_KEY"))
ALLOWED_HOSTS = validate_production_hosts(ALLOWED_HOSTS)  # noqa: F405

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Le frontend lit le cookie CSRF pour le renvoyer dans X-CSRFToken : ce cookie
# ne peut donc pas être HTTPOnly sans casser les mutations de session.
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = max(31536000, env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_flag("DJANGO_SECURE_HSTS_PRELOAD", True)
