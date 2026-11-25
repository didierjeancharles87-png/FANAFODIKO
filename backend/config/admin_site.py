from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model

from apps.accounts.models import ProfessionalVerificationRequest
from apps.accounts.models import AccountProfile


class FanafodikoAdminSite(AdminSite):
    site_header = "Administration FANAFODIKO"
    site_title = "FANAFODIKO"
    index_title = "Pilotage de la plateforme"
    index_template = "admin/index.html"

    def has_permission(self, request):
        if not super().has_permission(request):
            return False
        try:
            return request.user.account_profile.status == AccountProfile.Status.ACTIVE
        except AccountProfile.DoesNotExist:
            return False

    def index(self, request, extra_context=None):
        User = get_user_model()
        extra_context = extra_context or {}
        extra_context["dashboard_metrics"] = {
            "users_total": User.objects.count(),
            "users_active": User.objects.filter(is_active=True, account_profile__status="active").count(),
            "users_suspended": User.objects.filter(account_profile__status="suspended").count(),
            "users_disabled": User.objects.filter(is_active=False).count(),
            "professional_pending": ProfessionalVerificationRequest.objects.filter(status="pending").count(),
            "professional_approved": ProfessionalVerificationRequest.objects.filter(status="approved").count(),
        }
        return super().index(request, extra_context)

