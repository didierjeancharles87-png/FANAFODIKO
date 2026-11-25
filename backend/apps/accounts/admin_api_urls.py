from django.urls import path

from .views import AdminAccountListView, AdminDashboardView, AdminVerificationListView, AdminVerificationReviewView

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("accounts/", AdminAccountListView.as_view(), name="admin-account-list"),
    path("professional-verifications/", AdminVerificationListView.as_view(), name="admin-verification-list"),
    path("professional-verifications/<int:pk>/review/", AdminVerificationReviewView.as_view(), name="admin-verification-review"),
]
