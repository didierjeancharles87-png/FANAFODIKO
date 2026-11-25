from django.contrib.admin.apps import AdminConfig


class FanafodikoAdminConfig(AdminConfig):
    default_site = "config.admin_site.FanafodikoAdminSite"
