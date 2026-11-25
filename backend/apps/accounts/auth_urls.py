from django.urls import path

from .auth_views import CurrentUserView, CsrfCookieView, ProfessionalLoginView, ProfessionalLogoutView, ProfessionalRegistrationView
from .patient_views import PatientRegistrationView

urlpatterns = [
    path("csrf/", CsrfCookieView.as_view(), name="auth-csrf"),
    path("register/", ProfessionalRegistrationView.as_view(), name="professional-register"),
    path("register-patient/", PatientRegistrationView.as_view(), name="patient-register"),
    path("login/", ProfessionalLoginView.as_view(), name="professional-login"),
    path("logout/", ProfessionalLogoutView.as_view(), name="professional-logout"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
]
