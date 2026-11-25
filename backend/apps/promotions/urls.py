from django.urls import path

from .views import (
    AdminPromotionArchiveView,
    AdminPromotionListView,
    AdminPromotionReviewView,
    PartnerPromotionActivateView,
    PartnerPromotionDeactivateView,
    PartnerPromotionDetailView,
    PartnerPromotionListView,
    PartnerPromotionRemovalView,
    PartnerPromotionResultsView,
    PublicPromotionListView,
)


urlpatterns = [
    path("public/", PublicPromotionListView.as_view(), name="promotions-public-list"),
    path("partner/", PartnerPromotionListView.as_view(), name="promotions-partner-list"),
    path("partner/<int:pk>/", PartnerPromotionDetailView.as_view(), name="promotions-partner-detail"),
    path("partner/<int:pk>/activate/", PartnerPromotionActivateView.as_view(), name="promotions-partner-activate"),
    path("partner/<int:pk>/deactivate/", PartnerPromotionDeactivateView.as_view(), name="promotions-partner-deactivate"),
    path("partner/<int:pk>/request-removal/", PartnerPromotionRemovalView.as_view(), name="promotions-partner-removal"),
    path("partner/<int:pk>/results/", PartnerPromotionResultsView.as_view(), name="promotions-partner-results"),
    path("admin/", AdminPromotionListView.as_view(), name="promotions-admin-list"),
    path("admin/<int:pk>/approve/", AdminPromotionReviewView.as_view(), name="promotions-admin-approve"),
    path("admin/<int:pk>/reject/", AdminPromotionReviewView.as_view(approve=False), name="promotions-admin-reject"),
    path("admin/<int:pk>/archive/", AdminPromotionArchiveView.as_view(), name="promotions-admin-archive"),
]
