from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import BuyerAddress
from apps.marketplace.models import CatalogProduct
from apps.promotions.serializers import PromotionSummarySerializer
from apps.promotions.services import cart_pricing

from .models import Cart, CartItem, Order, OrderEvent, OrderItem
from .services import validate_orderable_product, validate_quantity


class CartAddSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=CatalogProduct.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=99)

    def validate_quantity(self, value):
        validate_quantity(value)
        return value

    def validate(self, attrs):
        try:
            validate_orderable_product(attrs["product"], attrs["quantity"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return attrs


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=99)

    def validate_quantity(self, value):
        validate_quantity(value)
        return value


class CartItemSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    seller_name = serializers.CharField(source="product.seller.name", read_only=True)
    unit_price_mga = serializers.SerializerMethodField()
    line_total_mga = serializers.SerializerMethodField()
    stock_quantity = serializers.IntegerField(source="product.stock_quantity", read_only=True)

    class Meta:
        model = CartItem
        fields = (
            "id", "product", "product_title", "seller_name", "quantity", "stock_quantity",
            "unit_price_mga", "line_total_mga", "created_at", "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_unit_price_mga(self, instance):
        return f"{instance.product.price_mga:.2f}"

    @extend_schema_field(serializers.CharField())
    def get_line_total_mga(self, instance):
        return f"{instance.product.price_mga * instance.quantity:.2f}"


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal_mga = serializers.SerializerMethodField()
    discount_mga = serializers.SerializerMethodField()
    total_mga = serializers.SerializerMethodField()
    coupon_code = serializers.CharField(source="applied_coupon_code", read_only=True)
    coupon_error = serializers.SerializerMethodField()
    promotion = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            "id", "items", "item_count", "subtotal_mga", "discount_mga", "total_mga",
            "coupon_code", "coupon_error", "promotion", "created_at", "updated_at",
        )
        read_only_fields = fields

    def pricing(self, instance):
        if not hasattr(self, "_pricing_cache"):
            self._pricing_cache = {}
        if instance.pk not in self._pricing_cache:
            self._pricing_cache[instance.pk] = cart_pricing(instance)
        return self._pricing_cache[instance.pk]

    @extend_schema_field(serializers.IntegerField())
    def get_item_count(self, instance):
        return instance.items.count()

    @extend_schema_field(serializers.CharField())
    def get_subtotal_mga(self, instance):
        return f"{self.pricing(instance)[1]:.2f}"

    @extend_schema_field(serializers.CharField())
    def get_discount_mga(self, instance):
        return f"{self.pricing(instance)[2]:.2f}"

    @extend_schema_field(serializers.CharField())
    def get_total_mga(self, instance):
        return f"{self.pricing(instance)[3]:.2f}"

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_coupon_error(self, instance):
        return self.pricing(instance)[4]

    @extend_schema_field(PromotionSummarySerializer(allow_null=True))
    def get_promotion(self, instance):
        if not instance.applied_promotion:
            return None
        return PromotionSummarySerializer(instance.applied_promotion).data


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "title", "unit_price_mga", "original_unit_price_mga", "discount_mga",
            "quantity", "line_total_mga", "coupon_code",
            "requires_prescription", "authorization_status", "authorization_reference",
            "prescription_checked_by_seller", "prescription_checked_at",
        )
        read_only_fields = fields


class OrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderEvent
        fields = ("id", "from_status", "to_status", "note", "created_at")
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    customer_username = serializers.CharField(source="customer.user.username", read_only=True)
    subtotal_mga = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_subtotal_mga(self, instance):
        value = instance.subtotal_mga if instance.subtotal_mga else instance.total_mga
        return f"{value:.2f}"

    class Meta:
        model = Order
        fields = (
            "id", "reference", "status", "subtotal_mga", "discount_mga", "total_mga", "coupon_code",
            "customer_note", "seller_note", "rejection_reason",
            "seller", "seller_name", "customer", "customer_username", "created_at", "updated_at",
            "accepted_at", "rejected_at", "preparing_at", "ready_at", "completed_at", "cancelled_at",
            "delivery_recipient", "delivery_phone", "delivery_country", "delivery_region", "delivery_city",
            "delivery_neighbourhood", "delivery_complement",
            "items", "events",
        )
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    customer_note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    delivery_address = serializers.PrimaryKeyRelatedField(
        queryset=BuyerAddress.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )


class TransitionNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AcceptOrderSerializer(TransitionNoteSerializer):
    prescription_checked = serializers.BooleanField(required=False, default=False)


class RejectOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, trim_whitespace=True)
