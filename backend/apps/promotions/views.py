from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsActiveAccount, IsCentralAdminWithPermission
from apps.audit.services import record_event
from apps.marketplace.permissions import IsPartnerOwner

from .models import DiscountType, Promotion, PromotionStatus
from .serializers import (
    CouponApplySerializer,
    PromotionDecisionSerializer,
    PromotionPublicSerializer,
    PromotionResultSerializer,
    PromotionSerializer,
    PromotionWriteSerializer,
)
from .services import (
    activate_promotion,
    archive_promotion,
    deactivate_promotion,
    promotion_results,
    public_promotion_queryset,
    request_promotion_removal,
    review_promotion,
)


def api_validation(exc):
    return exc.message_dict if hasattr(exc, "message_dict") else exc.messages


class PublicPromotionPagination(LimitOffsetPagination):
    default_limit = 12
    max_limit = 24


class PartnerPromotionMixin:
    permission_classes = (IsAuthenticated, IsActiveAccount, IsPartnerOwner)

    def owned_promotion(self, request, pk):
        promotion = get_object_or_404(
            Promotion.objects.filter(seller=request.partner_seller).select_related("product", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, promotion)
        return promotion


class PartnerPromotionListView(PartnerPromotionMixin, APIView):
    @extend_schema(responses=PromotionSerializer(many=True), summary="Lister les promotions de son vendeur", tags=["Promotions partenaire"])
    def get(self, request):
        promotions = Promotion.objects.filter(seller=request.partner_seller).select_related("product", "seller")
        return Response(PromotionSerializer(promotions, many=True, context={"request": request}).data)

    @extend_schema(request=PromotionWriteSerializer, responses=PromotionSerializer, summary="Créer une promotion soumise à validation", tags=["Promotions partenaire"])
    def post(self, request):
        serializer = PromotionWriteSerializer(data=request.data, context={"seller": request.partner_seller})
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        readable_value = f"{values['discount_value']:.2f}".rstrip("0").rstrip(".")
        discount_label = (
            f"-{readable_value} %"
            if values["discount_type"] == DiscountType.PERCENT
            else f"-{readable_value} Ar"
        )
        title = values.pop("title", "").strip() or f"PROMO {discount_label} — {values['product'].title}"
        promotion = Promotion(
            seller=request.partner_seller,
            created_by=request.user,
            updated_by=request.user,
            status=PromotionStatus.PENDING,
            title=title[:120],
            **values,
        )
        try:
            with transaction.atomic():
                promotion.full_clean()
                promotion.save()
                record_event(
                    actor=request.user,
                    action="promotions.promotion.submitted",
                    target=promotion,
                    request=request,
                    metadata={"code": promotion.code, "product_id": promotion.product_id},
                )
        except (DjangoValidationError, IntegrityError) as exc:
            raise ValidationError(api_validation(exc) if isinstance(exc, DjangoValidationError) else {"code": ["Ce code coupon est déjà utilisé."]}) from exc
        return Response(PromotionSerializer(promotion, context={"request": request}).data, status=status.HTTP_201_CREATED)


class PartnerPromotionDetailView(PartnerPromotionMixin, APIView):
    @extend_schema(responses=PromotionSerializer, summary="Consulter une promotion de son vendeur", tags=["Promotions partenaire"])
    def get(self, request, pk):
        return Response(PromotionSerializer(self.owned_promotion(request, pk), context={"request": request}).data)

    @extend_schema(request=PromotionWriteSerializer, responses=PromotionSerializer, summary="Modifier une promotion en attente ou refusée", tags=["Promotions partenaire"])
    def patch(self, request, pk):
        promotion = self.owned_promotion(request, pk)
        if promotion.status not in (PromotionStatus.PENDING, PromotionStatus.REJECTED):
            raise ValidationError({"status": "Cette promotion ne peut plus être modifiée."})
        serializer = PromotionWriteSerializer(
            promotion,
            data=request.data,
            partial=True,
            context={"seller": request.partner_seller, "instance": promotion},
        )
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        title = values.pop("title", "")
        for field, value in values.items():
            setattr(promotion, field, value)
        if title:
            promotion.title = title[:120]
        promotion.status = PromotionStatus.PENDING
        promotion.review_notes = ""
        promotion.reviewed_by = None
        promotion.reviewed_at = None
        promotion.updated_by = request.user
        try:
            with transaction.atomic():
                promotion.full_clean()
                promotion.save()
                record_event(
                    actor=request.user,
                    action="promotions.promotion.resubmitted",
                    target=promotion,
                    request=request,
                    metadata={"code": promotion.code},
                )
        except (DjangoValidationError, IntegrityError) as exc:
            raise ValidationError(api_validation(exc) if isinstance(exc, DjangoValidationError) else {"code": ["Ce code coupon est déjà utilisé."]}) from exc
        return Response(PromotionSerializer(promotion, context={"request": request}).data)


class PartnerPromotionActivateView(PartnerPromotionMixin, APIView):
    @extend_schema(request=None, responses=PromotionSerializer, summary="Activer une promotion validée", tags=["Promotions partenaire"])
    def post(self, request, pk):
        promotion = self.owned_promotion(request, pk)
        try:
            with transaction.atomic():
                updated = activate_promotion(Promotion.objects.select_for_update().get(pk=promotion.pk), actor=request.user)
                record_event(
                    actor=request.user,
                    action="promotions.promotion.activated",
                    target=updated,
                    request=request,
                    metadata={"code": updated.code},
                )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(PromotionSerializer(updated, context={"request": request}).data)


class PartnerPromotionDeactivateView(PartnerPromotionMixin, APIView):
    @extend_schema(request=None, responses=PromotionSerializer, summary="Désactiver une promotion active", tags=["Promotions partenaire"])
    def post(self, request, pk):
        promotion = self.owned_promotion(request, pk)
        try:
            with transaction.atomic():
                updated = deactivate_promotion(Promotion.objects.select_for_update().get(pk=promotion.pk), actor=request.user)
                record_event(
                    actor=request.user,
                    action="promotions.promotion.deactivated",
                    target=updated,
                    request=request,
                    metadata={"code": updated.code},
                )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(PromotionSerializer(updated, context={"request": request}).data)


class PartnerPromotionRemovalView(PartnerPromotionMixin, APIView):
    @extend_schema(request=None, responses=PromotionSerializer, summary="Demander l'archivage d'une promotion", tags=["Promotions partenaire"])
    def post(self, request, pk):
        promotion = self.owned_promotion(request, pk)
        try:
            with transaction.atomic():
                updated = request_promotion_removal(Promotion.objects.select_for_update().get(pk=promotion.pk), actor=request.user)
                record_event(
                    actor=request.user,
                    action="promotions.promotion.removal_requested",
                    target=updated,
                    request=request,
                    metadata={"code": updated.code},
                )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(PromotionSerializer(updated, context={"request": request}).data)


class PartnerPromotionResultsView(PartnerPromotionMixin, APIView):
    @extend_schema(responses=PromotionResultSerializer, summary="Consulter les résultats d'une promotion", tags=["Promotions partenaire"])
    def get(self, request, pk):
        promotion = self.owned_promotion(request, pk)
        payload = {
            "code": promotion.code,
            "title": promotion.title,
            "status": promotion.status,
            **promotion_results(promotion),
        }
        return Response(PromotionResultSerializer(payload).data)


class AdminPromotionListView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "promotions.view_promotion"

    @extend_schema(responses=PromotionSerializer(many=True), summary="Superviser toutes les promotions", tags=["Administration centrale"])
    def get(self, request):
        promotions = Promotion.objects.select_related("product", "seller").order_by("-created_at")
        return Response(PromotionSerializer(promotions, many=True, context={"request": request}).data)


class AdminPromotionReviewView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "promotions.change_promotion"
    approve = True

    @extend_schema(request=PromotionDecisionSerializer, responses=PromotionSerializer, summary="Valider ou refuser une promotion", tags=["Administration centrale"])
    def post(self, request, pk):
        promotion = get_object_or_404(Promotion.objects.select_related("product", "seller"), pk=pk)
        serializer = PromotionDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                locked = Promotion.objects.select_for_update().get(pk=promotion.pk)
                updated = review_promotion(
                    locked,
                    approve=self.approve,
                    reason=serializer.validated_data["reason"],
                    actor=request.user,
                )
                record_event(
                    actor=request.user,
                    action="promotions.promotion.approved" if self.approve else "promotions.promotion.rejected",
                    target=updated,
                    request=request,
                    metadata={"code": updated.code, "reason": updated.review_notes},
                )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(PromotionSerializer(updated, context={"request": request}).data)


class AdminPromotionArchiveView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "promotions.change_promotion"

    @extend_schema(request=None, responses=PromotionSerializer, summary="Archiver une promotion dont la suppression est demandée", tags=["Administration centrale"])
    def post(self, request, pk):
        promotion = get_object_or_404(Promotion.objects.select_related("product", "seller"), pk=pk)
        try:
            with transaction.atomic():
                locked = Promotion.objects.select_for_update().get(pk=promotion.pk)
                updated = archive_promotion(locked, actor=request.user)
                record_event(
                    actor=request.user,
                    action="promotions.promotion.archived",
                    target=updated,
                    request=request,
                    metadata={"code": updated.code},
                )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(PromotionSerializer(updated, context={"request": request}).data)


class PublicPromotionListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    pagination_class = PublicPromotionPagination

    @extend_schema(responses=PromotionPublicSerializer(many=True), summary="Lister les promotions publiques validées et actives", tags=["Catalogue public"])
    def get(self, request):
        promotions = public_promotion_queryset().prefetch_related(
            Prefetch("product__promotions", queryset=Promotion.objects.none())
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(promotions, request, view=self)
        data = PromotionPublicSerializer(page or [], many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)
