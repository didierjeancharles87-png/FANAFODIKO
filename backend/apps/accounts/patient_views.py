from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_event
from apps.core.throttling import RegistrationAccountRateThrottle, RegistrationIPRateThrottle
from .models import BuyerAddress
from .patient_serializers import BuyerAddressSerializer, PatientProfileSerializer, PatientRegistrationSerializer
from .permissions import IsActiveAccount, IsPatientAccount


class PatientRegistrationResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    roles = serializers.ListField(child=serializers.CharField())


class PatientRegistrationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = (RegistrationIPRateThrottle, RegistrationAccountRateThrottle)

    @extend_schema(
        request=PatientRegistrationSerializer,
        responses=PatientRegistrationResponseSerializer,
        summary="Créer un compte patient",
        tags=["Patients"],
    )
    def post(self, request):
        SessionAuthentication().enforce_csrf(request)
        serializer = PatientRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                login(request._request, user)
        except IntegrityError as exc:
            raise ValidationError({"email": ["Un compte existe déjà avec ces informations."]}) from exc
        record_event(actor=user, action="patient_session.opened", target=user.account_profile, request=request)
        return Response({"id": user.pk, "email": user.email, "roles": list(user.groups.values_list("name", flat=True))}, status=status.HTTP_201_CREATED)


class PatientProfileView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount, IsPatientAccount]

    @extend_schema(responses=PatientProfileSerializer, summary="Lire son profil patient", tags=["Patients"])
    def get(self, request):
        return Response(PatientProfileSerializer(request.user).data)

    @extend_schema(
        request=PatientProfileSerializer,
        responses=PatientProfileSerializer,
        summary="Modifier son profil patient",
        tags=["Patients"],
    )
    def patch(self, request):
        serializer = PatientProfileSerializer(request.user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BuyerAddressMixin:
    permission_classes = [IsAuthenticated, IsActiveAccount, IsPatientAccount]

    def owned_address(self, request, pk):
        return get_object_or_404(
            BuyerAddress.objects.filter(account=request.user.account_profile, is_active=True),
            pk=pk,
        )


class BuyerAddressListView(BuyerAddressMixin, APIView):
    @extend_schema(responses=BuyerAddressSerializer(many=True), summary="Lister ses adresses de retrait", tags=["Patients"])
    def get(self, request):
        addresses = BuyerAddress.objects.filter(account=request.user.account_profile, is_active=True)
        return Response(BuyerAddressSerializer(addresses, many=True).data)

    @extend_schema(request=BuyerAddressSerializer, responses=BuyerAddressSerializer, summary="Ajouter une adresse de retrait", tags=["Patients"])
    def post(self, request):
        serializer = BuyerAddressSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        address = serializer.save()
        record_event(actor=request.user, action="patient_address.created", target=address, request=request)
        return Response(BuyerAddressSerializer(address).data, status=status.HTTP_201_CREATED)


class BuyerAddressDetailView(BuyerAddressMixin, APIView):
    @extend_schema(responses=BuyerAddressSerializer, summary="Consulter une adresse de retrait", tags=["Patients"])
    def get(self, request, pk):
        return Response(BuyerAddressSerializer(self.owned_address(request, pk)).data)

    @extend_schema(request=BuyerAddressSerializer, responses=BuyerAddressSerializer, summary="Modifier une adresse de retrait", tags=["Patients"])
    def patch(self, request, pk):
        address = self.owned_address(request, pk)
        serializer = BuyerAddressSerializer(address, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        record_event(actor=request.user, action="patient_address.updated", target=updated, request=request)
        return Response(BuyerAddressSerializer(updated).data)

    @extend_schema(responses=serializers.Serializer, summary="Supprimer logiquement une adresse de retrait", tags=["Patients"])
    def delete(self, request, pk):
        address = self.owned_address(request, pk)
        with transaction.atomic():
            record_event(actor=request.user, action="patient_address.deleted", target=address, request=request)
            address.is_active = False
            address.is_primary = False
            address.save(update_fields=("is_active", "is_primary", "updated_at"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class BuyerAddressPrimaryView(BuyerAddressMixin, APIView):
    @extend_schema(request=None, responses=BuyerAddressSerializer, summary="Définir l'adresse de retrait principale", tags=["Patients"])
    def post(self, request, pk):
        address = self.owned_address(request, pk)
        with transaction.atomic():
            from django.utils import timezone

            BuyerAddress.objects.filter(account=request.user.account_profile, is_primary=True).update(
                is_primary=False, updated_at=timezone.now()
            )
            address.is_primary = True
            address.is_active = True
            address.save(update_fields=("is_primary", "is_active", "updated_at"))
            record_event(actor=request.user, action="patient_address.primary_set", target=address, request=request)
        return Response(BuyerAddressSerializer(address).data)
