from django.urls import path

from .views import ProfessionalVerificationCreateView
from .patient_views import (
    BuyerAddressDetailView,
    BuyerAddressListView,
    BuyerAddressPrimaryView,
    PatientProfileView,
)

urlpatterns = [
    path("professional-verifications/", ProfessionalVerificationCreateView.as_view(), name="my-professional-verifications"),
    path("patient/profile/", PatientProfileView.as_view(), name="patient-profile"),
    path("patient/addresses/", BuyerAddressListView.as_view(), name="patient-address-list"),
    path("patient/addresses/<int:pk>/", BuyerAddressDetailView.as_view(), name="patient-address-detail"),
    path("patient/addresses/<int:pk>/primary/", BuyerAddressPrimaryView.as_view(), name="patient-address-primary"),
]
