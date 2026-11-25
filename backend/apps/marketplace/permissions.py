from rest_framework.permissions import BasePermission

from apps.accounts.models import AccountProfile

from .models import CatalogSeller, SellerOwner


class IsPartnerOwner(BasePermission):
    """Autorise uniquement le compte explicitement attaché au vendeur concerné."""

    message = "Ce vendeur n’est pas attribué à votre compte."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_active:
            return False
        account = AccountProfile.objects.filter(user=user, user__is_active=True).first()
        if not account or account.status != AccountProfile.Status.ACTIVE:
            return False

        assignment = (
            SellerOwner.objects.select_related("seller", "account__user")
            .filter(account=account, seller__is_active=True)
            .first()
        )
        if not assignment:
            return False

        request.partner_owner_assignment = assignment
        request.partner_seller = assignment.seller
        return True

    def has_object_permission(self, request, view, obj):
        assignment = getattr(request, "partner_owner_assignment", None)
        if not assignment or not assignment.seller.is_active:
            return False
        seller_id = self._seller_id(obj)
        return seller_id is not None and seller_id == assignment.seller_id

    @staticmethod
    def _seller_id(obj):
        if isinstance(obj, CatalogSeller):
            return obj.pk
        seller_id = getattr(obj, "seller_id", None)
        if seller_id is not None:
            return seller_id
        product = getattr(obj, "product", None)
        return product.seller_id if product else None
