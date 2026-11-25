from django.urls import include, path

from apps.orders.views import AdminOrderListView

urlpatterns = [
    path("auth/", include("apps.accounts.auth_urls")),
    path("reference/", include("apps.reference.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("professionals/", include("apps.professionals.urls")),
    path("orders/", include("apps.orders.order_urls")),
    path("partner/orders/", include("apps.orders.partner_order_urls")),
    path("partner/", include("apps.marketplace.partner_urls")),
    path("cart/", include("apps.orders.cart_urls")),
    path("promotions/", include("apps.promotions.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("admin/marketplace/", include("apps.marketplace.admin_urls")),
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("admin/", include("apps.accounts.admin_api_urls")),
    path("site-content/", include("apps.sitecontent.urls")),
    path("marketplace/", include("apps.marketplace.urls")),
]
