from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminFAQViewSet, AdminImageViewSet, AdminNewsViewSet, AdminPageViewSet, AdminSiteConfigurationView, PublicFAQView, PublicNewsView, PublicPageView, PublicSiteConfigurationView, PublicSiteImageListView, PublicSiteImageView

router = DefaultRouter()
router.register("admin/faqs", AdminFAQViewSet, basename="site-admin-faq")
router.register("admin/news", AdminNewsViewSet, basename="site-admin-news")
router.register("admin/pages", AdminPageViewSet, basename="site-admin-page")
router.register("admin/images", AdminImageViewSet, basename="site-admin-image")

urlpatterns = [
    path("admin/configuration/", AdminSiteConfigurationView.as_view(), name="site-admin-configuration"),
    path("public/configuration/", PublicSiteConfigurationView.as_view(), name="site-public-configuration"),
    path("public/faqs/", PublicFAQView.as_view(), name="site-public-faqs"),
    path("public/news/", PublicNewsView.as_view(), name="site-public-news"),
    path("public/pages/<str:page>/", PublicPageView.as_view(), name="site-public-page"),
    path("public/images/", PublicSiteImageListView.as_view(), name="site-public-images"),
    path("public/images/<str:slot>/", PublicSiteImageView.as_view(), name="site-public-image"),
    path("", include(router.urls)),
]
