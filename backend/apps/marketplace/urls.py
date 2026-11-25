from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminCatalogProductImageView,
    AdminCatalogProductViewSet,
    AdminCatalogSellerViewSet,
    AdminMarketplaceOptionsView,
    PublicCatalogSearchView,
    PublicEquipmentListView,
    PublicMedicineListView,
    PublicProductDetailView,
    PublicProductImageFileView,
    PublicProductImageView,
)

router = SimpleRouter()
router.register("admin/sellers", AdminCatalogSellerViewSet, basename="marketplace-admin-sellers")
router.register("admin/products", AdminCatalogProductViewSet, basename="marketplace-admin-products")

urlpatterns = [
    path("public/medicines/", PublicMedicineListView.as_view(), name="marketplace-public-medicines"),
    path("public/equipment/", PublicEquipmentListView.as_view(), name="marketplace-public-equipment"),
    path("public/search/", PublicCatalogSearchView.as_view(), name="marketplace-public-search"),
    path("public/products/<slug:slug>/image/", PublicProductImageView.as_view(), name="marketplace-public-product-image"),
    path("public/products/<slug:slug>/images/<int:pk>/", PublicProductImageFileView.as_view(), name="marketplace-public-product-image-file"),
    path("public/products/<slug:slug>/", PublicProductDetailView.as_view(), name="marketplace-public-product-detail"),
    path("admin/options/", AdminMarketplaceOptionsView.as_view(), name="marketplace-admin-options"),
    path("admin/products/<int:pk>/image/", AdminCatalogProductImageView.as_view(), name="marketplace-admin-product-image"),
    path("", include(router.urls)),
]
