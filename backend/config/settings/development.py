import os

from .base import *  # noqa: F403

DEBUG = os.getenv("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
