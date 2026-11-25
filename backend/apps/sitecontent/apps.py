from django.apps import AppConfig


class SiteContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sitecontent"
    label = "sitecontent"
    verbose_name = "Contenus du site"
