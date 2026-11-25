from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile
from apps.accounts.permissions import IsActiveAccount

from .models import Notification
from .serializers import MarkReadSerializer, NotificationPreferenceSerializer, NotificationSerializer
from .services import get_or_create_preference, set_whatsapp_consent


class NotificationAccountMixin:
    permission_classes = (IsAuthenticated, IsActiveAccount)

    @staticmethod
    def current_account(request):
        account = AccountProfile.objects.filter(user=request.user, user__is_active=True).first()
        if not account or account.status != AccountProfile.Status.ACTIVE:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Ce compte n'est pas autorisé à consulter ses notifications.")
        return account


class NotificationListView(NotificationAccountMixin, generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.current_account(self.request)).select_related("recipient")

    @extend_schema(summary="Lister ses notifications réelles", tags=["Notifications"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class NotificationUnreadCountView(NotificationAccountMixin, APIView):
    @extend_schema(responses={200: {"type": "object", "properties": {"count": {"type": "integer"}}}}, summary="Nombre de notifications non lues", tags=["Notifications"])
    def get(self, request):
        count = Notification.objects.filter(recipient=self.current_account(request), read_at__isnull=True).count()
        return Response({"count": count})


class NotificationMarkReadView(NotificationAccountMixin, APIView):
    @extend_schema(request=MarkReadSerializer, responses=NotificationSerializer, summary="Marquer une notification comme lue", tags=["Notifications"])
    def post(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.filter(recipient=self.current_account(request)), pk=pk
        )
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=("read_at", "updated_at"))
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(NotificationAccountMixin, APIView):
    @extend_schema(request=MarkReadSerializer, responses={200: {"type": "object", "properties": {"updated": {"type": "integer"}}}}, summary="Marquer toutes ses notifications comme lues", tags=["Notifications"])
    def post(self, request):
        with transaction.atomic():
            queryset = Notification.objects.filter(
                recipient=self.current_account(request), read_at__isnull=True
            )
            updated = queryset.update(read_at=timezone.now(), updated_at=timezone.now())
        return Response({"updated": updated})


class NotificationPreferenceView(NotificationAccountMixin, APIView):
    @extend_schema(responses=NotificationPreferenceSerializer, summary="Lire ses préférences WhatsApp", tags=["Notifications"])
    def get(self, request):
        preference = get_or_create_preference(self.current_account(request))
        return Response(NotificationPreferenceSerializer(preference).data)

    @extend_schema(
        request=NotificationPreferenceSerializer,
        responses=NotificationPreferenceSerializer,
        summary="Modifier le consentement aux liens WhatsApp",
        tags=["Notifications"],
    )
    def patch(self, request):
        serializer = NotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "whatsapp_opt_in" not in serializer.validated_data:
            return Response(
                {"error": {"code": "missing_field", "message": "whatsapp_opt_in est obligatoire."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        preference = set_whatsapp_consent(
            self.current_account(request),
            enabled=serializer.validated_data["whatsapp_opt_in"],
            actor=request.user,
            request=request,
        )
        return Response(NotificationPreferenceSerializer(preference).data)
