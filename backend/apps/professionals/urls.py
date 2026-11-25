from django.urls import path

from .views import (
    AdminProfessionalAccountActionView,
    AdminProfessionalDocumentDownloadView,
    AdminProfessionalReactivateView,
    AdminProfessionalDocumentListView,
    AdminProfessionalProfileListView,
    MyProfessionalDocumentDeleteView,
    MyProfessionalDocumentDownloadView,
    MyProfessionalDocumentsView,
    MyProfessionalProfileView,
    ProfessionalCategoryListView,
    SubmitProfessionalProfileView,
)

urlpatterns = [
    path("categories/", ProfessionalCategoryListView.as_view(), name="professional-categories"),
    path("me/", MyProfessionalProfileView.as_view(), name="my-professional-profile"),
    path("me/submit/", SubmitProfessionalProfileView.as_view(), name="submit-professional-profile"),
    path("me/documents/", MyProfessionalDocumentsView.as_view(), name="my-professional-documents"),
    path("me/documents/<int:pk>/download/", MyProfessionalDocumentDownloadView.as_view(), name="my-professional-document-download"),
    path("me/documents/<int:pk>/", MyProfessionalDocumentDeleteView.as_view(), name="my-professional-document-delete"),
    path("admin/profiles/", AdminProfessionalProfileListView.as_view(), name="admin-professional-profiles"),
    path("admin/profiles/<int:pk>/suspend/", AdminProfessionalAccountActionView.as_view(action="suspend"), name="admin-professional-suspend"),
    path("admin/profiles/<int:pk>/reactivate/", AdminProfessionalReactivateView.as_view(), name="admin-professional-reactivate"),
    path("admin/documents/", AdminProfessionalDocumentListView.as_view(), name="admin-professional-documents"),
    path("admin/documents/<int:pk>/download/", AdminProfessionalDocumentDownloadView.as_view(), name="admin-professional-document-download"),
]
