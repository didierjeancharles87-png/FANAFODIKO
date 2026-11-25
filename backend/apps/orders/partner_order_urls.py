from django.urls import path

from .views import (
    PartnerOrderAcceptView,
    PartnerOrderCompleteView,
    PartnerOrderDetailView,
    PartnerOrderListView,
    PartnerOrderPrepareView,
    PartnerOrderReadyView,
    PartnerOrderRejectView,
)

urlpatterns = [
    path("", PartnerOrderListView.as_view(), name="partner-order-list"),
    path("<int:pk>/", PartnerOrderDetailView.as_view(), name="partner-order-detail"),
    path("<int:pk>/accept/", PartnerOrderAcceptView.as_view(), name="partner-order-accept"),
    path("<int:pk>/reject/", PartnerOrderRejectView.as_view(), name="partner-order-reject"),
    path("<int:pk>/prepare/", PartnerOrderPrepareView.as_view(), name="partner-order-prepare"),
    path("<int:pk>/mark-ready/", PartnerOrderReadyView.as_view(), name="partner-order-ready"),
    path("<int:pk>/complete/", PartnerOrderCompleteView.as_view(), name="partner-order-complete"),
]
