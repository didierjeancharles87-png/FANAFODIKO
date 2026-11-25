from django.urls import path

from .views import (
    PartnerDashboardView,
    PartnerProductAvailabilityView,
    PartnerProductDetailView,
    PartnerProductImageDetailView,
    PartnerProductImageFileView,
    PartnerProductImageView,
    PartnerProductImagePrimaryView,
    PartnerProductLegacyImageView,
    PartnerProductListView,
    PartnerProductPriceHistoryView,
    PartnerProductStockView,
    PartnerProductSubmitView,
    PartnerSellerDetailView,
)

urlpatterns = [
    path("dashboard/", PartnerDashboardView.as_view(), name="partner-dashboard"),
    path("sellers/<int:pk>/", PartnerSellerDetailView.as_view(), name="partner-seller-detail"),
    path("products/", PartnerProductListView.as_view(), name="partner-product-list"),
    path("products/<int:pk>/", PartnerProductDetailView.as_view(), name="partner-product-detail"),
    path("products/<int:pk>/submit/", PartnerProductSubmitView.as_view(), name="partner-product-submit"),
    path("products/<int:pk>/submit-review/", PartnerProductSubmitView.as_view(), name="partner-product-submit-review"),
    path("products/<int:pk>/stock/", PartnerProductStockView.as_view(), name="partner-product-stock"),
    path("products/<int:pk>/availability/", PartnerProductAvailabilityView.as_view(), name="partner-product-availability"),
    path("products/<int:pk>/price-history/", PartnerProductPriceHistoryView.as_view(), name="partner-product-price-history"),
    path("products/<int:pk>/image/", PartnerProductLegacyImageView.as_view(), name="partner-product-legacy-image"),
    path("products/<int:product_pk>/images/", PartnerProductImageView.as_view(), name="partner-product-images"),
    path(
        "products/<int:product_pk>/images/<int:pk>/",
        PartnerProductImageDetailView.as_view(),
        name="partner-product-image-detail",
    ),
    path(
        "products/<int:product_pk>/images/<int:pk>/file/",
        PartnerProductImageFileView.as_view(),
        name="partner-product-image-file",
    ),
    path(
        "products/<int:product_pk>/images/<int:pk>/primary/",
        PartnerProductImagePrimaryView.as_view(),
        name="partner-product-image-primary",
    ),
]
