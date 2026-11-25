from django.urls import path

from .views import (
    AdminAuthorizationDecisionView,
    AdminAuthorizationQueueView,
    AdminProductApproveView,
    AdminProductModerationListView,
    AdminProductPriceHistoryView,
    AdminProductRejectView,
    AdminSellerOwnerAssignmentView,
)

urlpatterns = [
    path("sellers/<int:pk>/assign-owner/", AdminSellerOwnerAssignmentView.as_view(), name="admin-marketplace-seller-assign-owner"),
    path("moderation/", AdminProductModerationListView.as_view(), name="admin-marketplace-moderation"),
    path("moderation/products/", AdminProductModerationListView.as_view(), name="admin-marketplace-moderation-products"),
    path("authorizations/", AdminAuthorizationQueueView.as_view(), name="admin-marketplace-authorizations"),
    path("products/<int:pk>/authorization/verify/", AdminAuthorizationDecisionView.as_view(decision="verify"), name="admin-marketplace-authorization-verify"),
    path("products/<int:pk>/authorization/reject/", AdminAuthorizationDecisionView.as_view(decision="reject"), name="admin-marketplace-authorization-reject"),
    path("products/<int:pk>/authorization/reopen/", AdminAuthorizationDecisionView.as_view(decision="reopen"), name="admin-marketplace-authorization-reopen"),
    path("products/<int:pk>/approve/", AdminProductApproveView.as_view(), name="admin-marketplace-product-approve"),
    path("products/<int:pk>/reject/", AdminProductRejectView.as_view(), name="admin-marketplace-product-reject"),
    path("products/<int:pk>/price-history/", AdminProductPriceHistoryView.as_view(), name="admin-marketplace-product-price-history"),
    path("price-history/<int:pk>/", AdminProductPriceHistoryView.as_view(), name="admin-marketplace-price-history"),
]
