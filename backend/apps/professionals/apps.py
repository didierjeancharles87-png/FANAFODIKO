from django.apps import AppConfig


class ProfessionalsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.professionals"
    label = "professionals"
    verbose_name = "Profils professionnels"

    def ready(self):
        from . import signals  # noqa: F401
