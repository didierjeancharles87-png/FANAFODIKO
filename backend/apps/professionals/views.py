from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes

from drf_spectacular.utils import extend_schema

from apps.accounts.categories import ProfessionalCategory
from apps.audit.services import record_event
from apps.core.pagination import AdminListPagination
from .models import ProfessionalDocument, ProfessionalProfile
from .permissions import IsStaffWithPermission
from .serializers import (
    AdminProfessionalDocumentSerializer,
    AdminProfessionalProfileSerializer,
    ProfessionalAccountStatusSerializer,
    ProfessionalCategorySerializer,
    ProfessionalDocumentSerializer,
    ProfessionalDocumentUploadSerializer,
    ProfessionalProfileSerializer,
)
from .services import set_professional_account_status, submit_professional_profile
from apps.accounts.permissions import IsActiveAccount


class ProfessionalCategoryListView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = ProfessionalCategorySerializer

    @extend_schema(responses=ProfessionalCategorySerializer(many=True), summary="Lister les catégories professionnelles", tags=["Profils professionnels"])
    def get(self, request):
        items = [{"code": value, "label": label} for value, label in ProfessionalCategory.choices]
        return Response(self.get_serializer(items, many=True).data)


class MyProfessionalProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfessionalProfileSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_object(self):
        return get_object_or_404(
            ProfessionalProfile.objects.select_related("account__user", "country", "verification_request").prefetch_related("documents"),
            account__user=self.request.user,
        )

    @transaction.atomic
    def perform_update(self, serializer):
        profile = serializer.save()
        profile.account.phone_number = profile.contact_phone
        profile.account.country = profile.country
        profile.account.save(update_fields=("phone_number", "country", "updated_at"))
        record_event(actor=self.request.user, action="professional_profile.updated", target=profile, request=self.request)


class SubmitProfessionalProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(request=None, responses=ProfessionalProfileSerializer, summary="Soumettre le profil à validation", tags=["Profils professionnels"])
    def post(self, request):
        profile = get_object_or_404(ProfessionalProfile, account__user=request.user)
        try:
            submit_professional_profile(profile=profile, actor=request.user, request=request)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"profile": exc.messages}) from exc
        return Response(ProfessionalProfileSerializer(profile).data)


class MyProfessionalDocumentsView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return ProfessionalDocument.objects.filter(profile__account__user=self.request.user).select_related("profile")

    def get_serializer_class(self):
        return ProfessionalDocumentUploadSerializer if self.request.method == "POST" else ProfessionalDocumentSerializer

    @extend_schema(responses=ProfessionalDocumentSerializer(many=True), summary="Lister ses justificatifs privés", tags=["Profils professionnels"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=ProfessionalDocumentUploadSerializer, responses={201: ProfessionalDocumentSerializer}, summary="Téléverser un justificatif privé (PDF/JPEG/PNG, 10 Mo maximum)", tags=["Profils professionnels"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        self.perform_create(input_serializer)
        output_data = ProfessionalDocumentSerializer(input_serializer.instance).data
        headers = self.get_success_headers(output_data)
        return Response(output_data, status=status.HTTP_201_CREATED, headers=headers)

    @transaction.atomic
    def perform_create(self, serializer):
        profile = get_object_or_404(ProfessionalProfile, account__user=self.request.user)
        if profile.verification_status == ProfessionalProfile.VerificationStatus.PENDING:
            raise ValidationError("Un justificatif ne peut pas être ajouté pendant l’examen du profil.")
        if profile.verification_status in (ProfessionalProfile.VerificationStatus.APPROVED, ProfessionalProfile.VerificationStatus.REJECTED):
            profile.verification_status = ProfessionalProfile.VerificationStatus.DRAFT
            profile.verification_request = None
            profile.save(update_fields=("verification_status", "verification_request", "updated_at"))
            profile.account.user.groups.remove(*profile.account.user.groups.filter(name="professional_verified"))
        uploaded = serializer.validated_data["file"]
        document = serializer.save(
            profile=profile,
            original_filename=uploaded._fanafodiko_safe_name,
            content_type=uploaded._fanafodiko_detected_type,
            size_bytes=uploaded.size,
        )
        record_event(actor=self.request.user, action="professional_document.uploaded", target=document, request=self.request)


class MyProfessionalDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}, summary="Télécharger un de ses justificatifs privés", tags=["Profils professionnels"])
    def get(self, request, pk):
        document = get_object_or_404(ProfessionalDocument.objects.select_related("profile"), pk=pk, profile__account__user=request.user)
        return stream_document(document, actor=request.user, request=request)


class MyProfessionalDocumentDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]
    serializer_class = ProfessionalDocumentSerializer

    def get_queryset(self):
        return ProfessionalDocument.objects.filter(profile__account__user=self.request.user).select_related("profile", "profile__account__user")

    @transaction.atomic
    def perform_destroy(self, document):
        profile = document.profile
        if profile.verification_status == ProfessionalProfile.VerificationStatus.PENDING:
            raise ValidationError("Un justificatif ne peut pas être supprimé pendant l’examen du profil.")
        if profile.verification_status == ProfessionalProfile.VerificationStatus.APPROVED:
            profile.verification_status = ProfessionalProfile.VerificationStatus.DRAFT
            profile.verification_request = None
            profile.save(update_fields=("verification_status", "verification_request", "updated_at"))
            profile.account.user.groups.remove(*profile.account.user.groups.filter(name="professional_verified"))
        record_event(actor=self.request.user, action="professional_document.deleted", target=document, request=self.request)
        document.delete()


def stream_document(document, *, actor, request=None):
    record_event(actor=actor, action="professional_document.downloaded", target=document, request=request)
    response = FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.original_filename,
        content_type=document.content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class AdminProfessionalProfileListView(generics.ListAPIView):
    serializer_class = AdminProfessionalProfileSerializer
    permission_classes = [IsStaffWithPermission, IsActiveAccount]
    required_permission = "professionals.view_professionalprofile"
    pagination_class = AdminListPagination
    queryset = ProfessionalProfile.objects.select_related("account__user", "account", "country").prefetch_related("documents")

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get("category")
        state = self.request.query_params.get("status")
        if category:
            if category not in ProfessionalCategory.values:
                raise ValidationError({"category": "Catégorie inconnue."})
            queryset = queryset.filter(category=category)
        if state:
            if state not in ProfessionalProfile.VerificationStatus.values:
                raise ValidationError({"status": "Statut de validation inconnu."})
            queryset = queryset.filter(verification_status=state)
        return queryset

    @extend_schema(summary="Lister les profils professionnels pour l’administration", tags=["Administration professionnelle"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminProfessionalAccountActionView(APIView):
    permission_classes = [IsStaffWithPermission, IsActiveAccount]
    required_permission = "professionals.change_professionalprofile"
    action = None

    @extend_schema(request=ProfessionalAccountStatusSerializer, responses=AdminProfessionalProfileSerializer, summary="Suspendre un compte professionnel", tags=["Administration professionnelle"])
    def post(self, request, pk, action=None):
        action = action or self.action
        profile = get_object_or_404(ProfessionalProfile.objects.select_related("account__user"), pk=pk)
        serializer = ProfessionalAccountStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = "suspended" if action == "suspend" else "active"
        try:
            set_professional_account_status(
                profile=profile,
                actor=request.user,
                status=target_status,
                reason=serializer.validated_data.get("reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"status": exc.messages}) from exc
        return Response(AdminProfessionalProfileSerializer(profile).data)


class AdminProfessionalReactivateView(AdminProfessionalAccountActionView):
    action = "reactivate"

    @extend_schema(request=ProfessionalAccountStatusSerializer, responses=AdminProfessionalProfileSerializer, summary="Réactiver un compte professionnel suspendu", tags=["Administration professionnelle"])
    def post(self, request, pk):
        return super().post(request, pk, action="reactivate")


class AdminProfessionalDocumentListView(generics.ListAPIView):
    serializer_class = AdminProfessionalDocumentSerializer
    permission_classes = [IsStaffWithPermission, IsActiveAccount]
    required_permission = "professionals.view_professionaldocument"
    pagination_class = AdminListPagination
    queryset = ProfessionalDocument.objects.select_related("profile", "profile__account__user")

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            if category not in ProfessionalCategory.values:
                raise ValidationError({"category": "Catégorie inconnue."})
            queryset = queryset.filter(profile__category=category)
        review_status = self.request.query_params.get("review_status")
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        return queryset

    @extend_schema(summary="Lister les justificatifs professionnels privés", tags=["Administration professionnelle"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminProfessionalDocumentDownloadView(APIView):
    permission_classes = [IsStaffWithPermission, IsActiveAccount]
    required_permission = "professionals.view_professionaldocument"

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}, summary="Télécharger un justificatif privé avec accès administrateur", tags=["Administration professionnelle"])
    def get(self, request, pk):
        document = get_object_or_404(ProfessionalDocument.objects.select_related("profile"), pk=pk)
        return stream_document(document, actor=request.user, request=request)
