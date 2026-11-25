from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission

from .models import AccountProfile
from .services import LOGOUT_ONLY_SESSION_KEY


class IsActiveAccount(BasePermission):
    message = "Ce compte n’est pas autorisé à accéder à cette ressource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            return user.is_active and user.account_profile.status == "active"
        except AccountProfile.DoesNotExist:
            return False


class IsCentralAdminWithPermission(BasePermission):
    """Permission explicite de l’administration centrale.

    Un compte ``is_staff`` n’obtient aucun droit automatiquement : il doit
    posséder la permission Django associée à la fonctionnalité. Les
    superutilisateurs conservent leurs fonctions via ``is_superuser``.
    """

    message = "Vous n’avez pas la permission nécessaire pour cette opération."

    def _required_permission(self, request, view):
        permission = getattr(view, "required_permission", None)

        by_action = getattr(view, "required_permission_by_action", None)
        action = getattr(view, "action", None)
        if by_action and action in by_action:
            return by_action[action]

        by_method = getattr(view, "required_permission_by_method", None)
        if by_method:
            method_permission = by_method.get(request.method.lower())
            if method_permission:
                return method_permission

        return permission

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if not (user.is_superuser or user.is_staff):
            return False

        permission = self._required_permission(request, view)
        return bool(permission and user.has_perm(permission))


class IsLogoutSessionAllowed(BasePermission):
    """Autorise le logout pour une session active ou une session révoquée.

    Une session révoquée ne contient que ``logout_only_user_id`` : elle ne
    authentifie pas l'utilisateur et ne doit jamais permettre un autre endpoint.
    """

    message = "Cette session ne peut être utilisée que pour la déconnexion."

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated:
            return True

        session = getattr(request, "session", None)
        user_id = session.get(LOGOUT_ONLY_SESSION_KEY) if session else None
        if not user_id:
            return False

        user_model = get_user_model()
        try:
            target = user_model.objects.get(pk=user_id)
        except (user_model.DoesNotExist, TypeError, ValueError):
            return False

        if not target.is_active:
            return True
        try:
            return target.account_profile.status != AccountProfile.Status.ACTIVE
        except AccountProfile.DoesNotExist:
            return True


class IsPatientAccount(BasePermission):
    message = "Cette ressource est réservée aux comptes patients."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.groups.filter(name="patient").exists())
