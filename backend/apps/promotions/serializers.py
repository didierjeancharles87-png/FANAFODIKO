from decimal import Decimal

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.marketplace.models import CatalogProduct

from .models import DiscountType, Promotion
from .services import derive_promotion_prices, normalize_coupon_code


class PromotionWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=CatalogProduct.objects.all())
    code = serializers.CharField(max_length=32, trim_whitespace=True)
    title = serializers.CharField(max_length=120, trim_whitespace=True, required=False, allow_blank=True)
    discount_type = serializers.ChoiceField(choices=DiscountType.choices)
    discount_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    max_redemptions = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_code(self, value):
        code = normalize_coupon_code(value)
        instance = self.context.get("instance")
        query = Promotion.objects.filter(code__iexact=code)
        if instance and instance.pk:
            query = query.exclude(pk=instance.pk)
        if query.exists():
            raise serializers.ValidationError("Ce code coupon est déjà utilisé.")
        return code

    def validate(self, attrs):
        instance = self.context.get("instance")
        product = attrs.get("product") or (instance.product if instance else None)
        seller = self.context.get("seller") or (instance.seller if instance else None)
        if product is None:
            raise serializers.ValidationError({"product": "Ce produit est obligatoire."})
        if seller and product.seller_id != seller.pk:
            raise serializers.ValidationError({"product": "Ce produit n’appartient pas à votre vendeur."})
        if product.status == CatalogProduct.Status.ARCHIVED:
            raise serializers.ValidationError({"product": "Ce produit est archivé."})
        starts_at = attrs.get("starts_at") or (instance.starts_at if instance else None)
        ends_at = attrs.get("ends_at") or (instance.ends_at if instance else None)
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "La date de fin doit être postérieure à la date de début."})
        discount_type = attrs.get("discount_type") or (instance.discount_type if instance else None)
        discount_value = attrs.get("discount_value") or (instance.discount_value if instance else None)
        if discount_type and discount_value:
            original, promotional = derive_promotion_prices(
                original_price=product.price_mga,
                discount_type=discount_type,
                discount_value=discount_value,
            )
            attrs["original_price_mga"] = original
            attrs["promotional_price_mga"] = promotional
        return attrs


class PromotionSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    discount_type_label = serializers.CharField(source="get_discount_type_display", read_only=True)
    discount_label = serializers.CharField(read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    remaining_quantity = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Promotion
        fields = (
            "id", "code", "title", "seller", "seller_name", "product", "product_title", "product_slug",
            "discount_type", "discount_type_label", "discount_value", "discount_label",
            "original_price_mga", "promotional_price_mga", "starts_at", "ends_at",
            "max_redemptions", "redemption_count", "remaining_quantity", "status", "status_label",
            "review_notes", "reviewed_at", "created_at", "updated_at",
        )
        read_only_fields = fields


class PromotionPublicSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_type = serializers.CharField(source="product.product_type", read_only=True)
    image_url = serializers.SerializerMethodField()
    discount_label = serializers.CharField(read_only=True)
    remaining_quantity = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Promotion
        fields = (
            "id", "code", "title", "product", "product_title", "product_slug", "product_type", "image_url",
            "discount_type", "discount_label", "discount_value", "original_price_mga", "promotional_price_mga",
            "starts_at", "ends_at", "max_redemptions", "remaining_quantity",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, instance):
        if not instance.product.image:
            return None
        path = f"/api/v1/marketplace/public/products/{instance.product.slug}/image/"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class PromotionSummarySerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    discount_label = serializers.CharField(read_only=True)

    class Meta:
        model = Promotion
        fields = (
            "id", "code", "title", "product", "product_title", "discount_label",
            "original_price_mga", "promotional_price_mga", "status",
        )
        read_only_fields = fields


class PromotionResultSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()
    redemption_count = serializers.IntegerField()
    quantity_used = serializers.IntegerField()
    total_discount_mga = serializers.CharField()
    remaining_quantity = serializers.IntegerField(allow_null=True)


class CouponApplySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32, trim_whitespace=True)

    def validate_code(self, value):
        return normalize_coupon_code(value)


class PromotionDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, trim_whitespace=True, required=False, allow_blank=True, default="")
