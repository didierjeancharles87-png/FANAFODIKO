from django.urls import path

from .views import CartCouponView, CartItemDetailView, CartView

urlpatterns = [
    path("", CartView.as_view(), name="cart-detail"),
    path("coupon/", CartCouponView.as_view(), name="cart-coupon"),
    path("items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
