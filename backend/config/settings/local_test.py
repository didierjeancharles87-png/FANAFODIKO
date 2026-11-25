"""Isolated local functional-test settings.

This module uses a dedicated SQLite scratch database and scratch media directory.
It never touches the project PostgreSQL database and never runs migrations on it.
"""

from .development import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "local-test.sqlite3",  # noqa: F405
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = BASE_DIR / "local-test-media"  # noqa: F405
MEDIA_URL = "/local-test-media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
