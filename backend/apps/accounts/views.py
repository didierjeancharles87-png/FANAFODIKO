from django.core.exceptions import ValidationError
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .models import AccountProfile, ProfessionalVerificationRequest
from .permissions import IsActiveAccount, IsCentralAdminWithPermission
from .serializers import AccountListSerializer, AdminDashboardSerializer, ProfessionalVerificationRequestSerializer, VerificationReviewSerializer
from .services import review_professional_request
from apps.audit.services import record_event
from apps.core.pagination import AdminListPagination


class ProfessionalVerificationCreateView(generics.ListCreateAPIView):
    serializer_class = ProfessionalVerificationRequestSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_queryset(self):
        return ProfessionalVerificationRequest.objects.filter(user=self.request.user).select_related("country")

    @transaction.atomic
    def perform_create(self, serializer):
        verification = serializer.save()
        pending_role, _ = Group.objects.get_or_create(name="professional_pending")
        verification.user.groups.add(pending_role)
        record_event(actor=self.request.user, action="professional_verification.submitted", target=verification, request=self.request)

    @extend_schema(summary="Soumettre une demande de validation professionnelle", tags=["Comptes"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    @extend_schema(summary="Lister ses demandes de validation professionnelle", tags=["Comptes"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminDashboardView(APIView):
    permission_classes = [IsCentralAdminWithPermission, IsActiveAccount]
    required_permission = "accounts.view_accountprofile"

    @extend_schema(responses=AdminDashboardSerializer, summary="Consulter les indicateurs de la plateforme", tags=["Administration"])
    def get(self, request):
        profiles = AccountProfile.objects.values("status").annotate(total=Count("id"))
        account_counts = {row["status"]: row["total"] for row in profiles}
        verifications = ProfessionalVerificationRequest.objects.values("status").annotate(total=Count("id"))
        verification_counts = {row["status"]: row["total"] for row in verifications}
        return Response({
            "users": {
                "total": get_user_model().objects.count(),
                "active": AccountProfile.objects.filter(status=AccountProfile.Status.ACTIVE, user__is_active=True).count(),
                "suspended": account_counts.get(AccountProfile.Status.SUSPENDED, 0),
                "closed": account_counts.get(AccountProfile.Status.CLOSED, 0),
                "disabled": AccountProfile.objects.filter(user__is_active=False).count(),
            },
            "professional_verifications": {
                "pending": verification_counts.get(ProfessionalVerificationRequest.Status.PENDING, 0),
                "approved": verification_counts.get(ProfessionalVerificationRequest.Status.APPROVED, 0),
                "rejected": verification_counts.get(ProfessionalVerificationRequest.Status.REJECTED, 0),
            },
        })


class AdminAccountListView(generics.ListAPIView):
    serializer_class = AccountListSerializer
    permission_classes = [IsCentralAdminWithPermission, IsActiveAccount]
    required_permission = "accounts.view_accountprofile"
    pagination_class = AdminListPagination

    def get_queryset(self):
        User = AccountProfile._meta.get_field("user").remote_field.model
        queryset = User.objects.select_related("account_profile").prefetch_related("groups").order_by("id")
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter not in AccountProfile.Status.values:
            raise APIValidationError({"status": "Statut de compte inconnu."})
        if status_filter in AccountProfile.Status.values:
            queryset = queryset.filter(account_profile__status=status_filter)
        return queryset

    @extend_schema(summary="Lister les comptes de la plateforme", tags=["Administration"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminVerificationListView(generics.ListAPIView):
    serializer_class = ProfessionalVerificationRequestSerializer
    permission_classes = [IsCentralAdminWithPermission, IsActiveAccount]
    required_permission = "accounts.view_professionalverificationrequest"
    pagination_class = AdminListPagination
    queryset = ProfessionalVerificationRequest.objects.select_related("user", "country", "reviewed_by")

    @extend_schema(summary="Lister les demandes professionnelles", tags=["Administration"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminVerificationReviewView(APIView):
    permission_classes = [IsCentralAdminWithPermission, IsActiveAccount]
    required_permission = "accounts.change_professionalverificationrequest"

    @extend_schema(request=VerificationReviewSerializer, responses=ProfessionalVerificationRequestSerializer, summary="Examiner une demande professionnelle", tags=["Administration"])
    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        verification = get_object_or_404(ProfessionalVerificationRequest, pk=pk)
        serializer = VerificationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            verification = review_professional_request(
                verification=verification,
                actor=request.user,
                status=serializer.validated_data["status"],
                notes=serializer.validated_data.get("notes", ""),
                request=request,
            )
        except ValidationError as exc:
            raise APIValidationError({"review": exc.messages}) from exc
        return Response(ProfessionalVerificationRequestSerializer(verification).data)
