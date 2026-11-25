from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AccountProfile
from apps.accounts.permissions import IsActiveAccount, IsCentralAdminWithPermission, IsPatientAccount
from apps.audit.services import record_event
from apps.core.throttling import CouponAccountRateThrottle, CouponIPRateThrottle
from apps.marketplace.permissions import IsPartnerOwner
from apps.promotions.serializers import CouponApplySerializer
from apps.promotions.services import apply_coupon_to_cart, clear_coupon_from_cart

from .models import Cart, CartItem, Order, OrderStatus
from .serializers import (
    AcceptOrderSerializer,
    CartAddSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
    CheckoutSerializer,
    OrderSerializer,
    RejectOrderSerializer,
    TransitionNoteSerializer,
)
from .services import add_cart_item, checkout, get_or_create_cart, transition_order, update_cart_item


def api_validation(exc):
    return exc.message_dict if hasattr(exc, "message_dict") else exc.messages


class CartOwnedMixin:
    permission_classes = (IsAuthenticated, IsActiveAccount, IsPatientAccount)

    @staticmethod
    def current_account(request):
        account = AccountProfile.objects.filter(user=request.user, user__is_active=True).first()
        if not account or account.status != AccountProfile.Status.ACTIVE:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Ce compte n’est pas autorisé à utiliser le panier.")
        return account

    def owned_cart(self, request):
        return get_or_create_cart(self.current_account(request))

    def serialize_cart(self, request, cart=None):
        cart = cart or self.owned_cart(request)
        cart = Cart.objects.prefetch_related("items__product__seller").get(pk=cart.pk)
        return CartSerializer(cart, context={"request": request}).data


class CartView(CartOwnedMixin, APIView):
    @extend_schema(responses=CartSerializer, summary="Consulter son panier serveur", tags=["Panier"])
    def get(self, request):
        return Response(self.serialize_cart(request))

    @extend_schema(request=CartAddSerializer, responses=CartSerializer, summary="Ajouter ou remplacer un article du panier", tags=["Panier"])
    def post(self, request):
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = add_cart_item(
                account=self.current_account(request),
                product_id=serializer.validated_data["product"].pk,
                quantity=serializer.validated_data["quantity"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        record_event(
            actor=request.user,
            action="cart.item.added",
            target=item,
            request=request,
            metadata={"product_id": item.product_id, "quantity": item.quantity},
        )
        return Response(self.serialize_cart(request, item.cart), status=status.HTTP_201_CREATED)

    @extend_schema(responses=CartSerializer, summary="Vider son panier serveur", tags=["Panier"])
    def delete(self, request):
        cart = self.owned_cart(request)
        with transaction.atomic():
            record_event(
                actor=request.user,
                action="cart.cleared",
                target=cart,
                request=request,
                metadata={"removed_items": cart.items.count()},
            )
            cart.items.all().delete()
        return Response(self.serialize_cart(request, cart))


class CartItemDetailView(CartOwnedMixin, APIView):
    def owned_item(self, request, pk):
        return get_object_or_404(
            CartItem.objects.select_related("product__seller", "cart__account").filter(cart__account=self.current_account(request)),
            pk=pk,
        )

    @extend_schema(request=CartItemUpdateSerializer, responses=CartSerializer, summary="Modifier la quantité d’un article", tags=["Panier"])
    def patch(self, request, pk):
        item = self.owned_item(request, pk)
        serializer = CartItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "quantity" not in serializer.validated_data:
            raise ValidationError({"quantity": "Ce champ est obligatoire."})
        try:
            updated = update_cart_item(
                account=self.current_account(request),
                item_id=item.pk,
                quantity=serializer.validated_data["quantity"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        record_event(
            actor=request.user,
            action="cart.item.updated",
            target=updated,
            request=request,
            metadata={"product_id": updated.product_id, "quantity": updated.quantity},
        )
        return Response(self.serialize_cart(request, updated.cart))

    @extend_schema(responses=CartSerializer, summary="Retirer un article du panier", tags=["Panier"])
    def delete(self, request, pk):
        item = self.owned_item(request, pk)
        cart = item.cart
        with transaction.atomic():
            record_event(
                actor=request.user,
                action="cart.item.removed",
                target=item,
                request=request,
                metadata={"product_id": item.product_id, "quantity": item.quantity},
            )
            item.delete()
        return Response(self.serialize_cart(request, cart))


class CouponThrottleMixin:
    """Limite seulement l'application d'un coupon, pas sa consultation/retrait."""

    throttle_classes = (CouponIPRateThrottle, CouponAccountRateThrottle)

    def get_throttles(self):
        if self.request.method != "POST":
            return []
        return super().get_throttles()


class CartCouponView(CouponThrottleMixin, CartOwnedMixin, APIView):
    @extend_schema(request=CouponApplySerializer, responses=CartSerializer, summary="Appliquer un coupon au panier", tags=["Panier"])
    def post(self, request):
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            promotion = apply_coupon_to_cart(self.owned_cart(request), serializer.validated_data["code"])
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        record_event(
            actor=request.user,
            action="cart.coupon.applied",
            target=promotion,
            request=request,
            metadata={"code": promotion.code},
        )
        return Response(self.serialize_cart(request))

    @extend_schema(responses=CartSerializer, summary="Retirer le coupon du panier", tags=["Panier"])
    def delete(self, request):
        cart = clear_coupon_from_cart(self.owned_cart(request))
        record_event(actor=request.user, action="cart.coupon.removed", target=cart, request=request)
        return Response(self.serialize_cart(request, cart))


class ClientOrderMixin(CartOwnedMixin):
    def order_queryset(self, request):
        return Order.objects.filter(customer=self.current_account(request))

    def owned_order(self, request, pk):
        return get_object_or_404(
            self.order_queryset(request).select_related("seller", "customer__user").prefetch_related("items", "events"),
            pk=pk,
        )


class ClientOrderListView(ClientOrderMixin, APIView):
    @extend_schema(responses=OrderSerializer(many=True), summary="Lister ses réservations", tags=["Commandes client"])
    def get(self, request):
        orders = self.order_queryset(request).select_related("seller", "customer__user").prefetch_related("items", "events")
        return Response(OrderSerializer(orders, many=True, context={"request": request}).data)

    @extend_schema(request=CheckoutSerializer, responses=OrderSerializer(many=True), summary="Confirmer une réservation sans paiement en ligne", tags=["Commandes client"])
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            orders = checkout(
                account=self.current_account(request),
                actor=request.user,
                customer_note=serializer.validated_data["customer_note"],
                delivery_address=serializer.validated_data.get("delivery_address"),
                request=request,
            )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        orders = Order.objects.filter(pk__in=[order.pk for order in orders]).select_related(
            "seller", "customer__user"
        ).prefetch_related("items", "events")
        return Response(OrderSerializer(orders, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ClientOrderDetailView(ClientOrderMixin, APIView):
    @extend_schema(responses=OrderSerializer, summary="Consulter une réservation client", tags=["Commandes client"])
    def get(self, request, pk):
        order = self.owned_order(request, pk)
        return Response(OrderSerializer(order, context={"request": request}).data)


class ClientOrderCancelView(ClientOrderMixin, APIView):
    @extend_schema(request=TransitionNoteSerializer, responses=OrderSerializer, summary="Annuler sa réservation avant acceptation", tags=["Commandes client"])
    def post(self, request, pk):
        order = self.owned_order(request, pk)
        serializer = TransitionNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = transition_order(
                order,
                to_status=OrderStatus.CANCELLED,
                actor=request.user,
                request=request,
                note=serializer.validated_data["note"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(OrderSerializer(updated, context={"request": request}).data)


class AdminOrderListView(APIView):
    permission_classes = (IsCentralAdminWithPermission, IsActiveAccount)
    required_permission = "orders.view_order"

    @extend_schema(responses=OrderSerializer(many=True), summary="Superviser toutes les réservations", tags=["Administration"])
    def get(self, request):
        orders = Order.objects.select_related("seller", "customer__user").prefetch_related("items", "events")
        return Response(OrderSerializer(orders, many=True, context={"request": request}).data)


class PartnerOrderMixin:
    permission_classes = (IsAuthenticated, IsActiveAccount, IsPartnerOwner)

    def owned_order(self, request, pk):
        order = get_object_or_404(
            Order.objects.filter(seller=request.partner_seller)
            .select_related("seller", "customer__user")
            .prefetch_related("items", "events"),
            pk=pk,
        )
        self.check_object_permissions(request, order)
        return order


class PartnerOrderListView(PartnerOrderMixin, APIView):
    @extend_schema(responses=OrderSerializer(many=True), summary="Lister les commandes de son vendeur", tags=["Espace partenaire"])
    def get(self, request):
        orders = Order.objects.filter(seller=request.partner_seller).select_related(
            "seller", "customer__user"
        ).prefetch_related("items", "events")
        return Response(OrderSerializer(orders, many=True, context={"request": request}).data)


class PartnerOrderDetailView(PartnerOrderMixin, APIView):
    @extend_schema(responses=OrderSerializer, summary="Consulter une commande partenaire", tags=["Espace partenaire"])
    def get(self, request, pk):
        return Response(OrderSerializer(self.owned_order(request, pk), context={"request": request}).data)


class PartnerOrderTransitionView(PartnerOrderMixin, APIView):
    target_status = None
    request_serializer = TransitionNoteSerializer

    @extend_schema(request=TransitionNoteSerializer, responses=OrderSerializer, summary="Changer le statut d’une commande", tags=["Espace partenaire"])
    def post(self, request, pk):
        order = self.owned_order(request, pk)
        serializer = self.request_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        reason = values.pop("reason", "")
        prescription_checked = values.pop("prescription_checked", False)
        try:
            updated = transition_order(
                order,
                to_status=self.target_status,
                actor=request.user,
                request=request,
                reason=reason,
                prescription_checked=prescription_checked,
                **values,
            )
        except DjangoValidationError as exc:
            raise ValidationError(api_validation(exc)) from exc
        return Response(OrderSerializer(updated, context={"request": request}).data)


class PartnerOrderAcceptView(PartnerOrderTransitionView):
    target_status = OrderStatus.ACCEPTED
    request_serializer = AcceptOrderSerializer


class PartnerOrderRejectView(PartnerOrderTransitionView):
    target_status = OrderStatus.REJECTED
    request_serializer = RejectOrderSerializer


class PartnerOrderPrepareView(PartnerOrderTransitionView):
    target_status = OrderStatus.PREPARING


class PartnerOrderReadyView(PartnerOrderTransitionView):
    target_status = OrderStatus.READY


class PartnerOrderCompleteView(PartnerOrderTransitionView):
    target_status = OrderStatus.COMPLETED
