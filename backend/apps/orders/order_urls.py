from django.urls import path

from .views import ClientOrderCancelView, ClientOrderDetailView, ClientOrderListView

urlpatterns = [
    path("", ClientOrderListView.as_view(), name="order-list"),
    path("<int:pk>/", ClientOrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/cancel/", ClientOrderCancelView.as_view(), name="order-cancel"),
]
