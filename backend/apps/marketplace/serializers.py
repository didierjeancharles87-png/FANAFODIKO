from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import AccountProfile
from apps.audit.services import record_event
from apps.notifications.services import notify_stock_depleted
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country
from apps.promotions.serializers import PromotionPublicSerializer
from apps.promotions.services import public_promotion_queryset
from .models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory, SellerOwner
from .services import record_price_change, set_primary_product_image, sync_primary_image
from .validation import product_image_content_type, validate_product_image_file


class CatalogSellerAdminSerializer(serializers.ModelSerializer):
    verification_status_label = serializers.CharField(source="get_verification_status_display", read_only=True)
    country_name = serializers.CharField(source="country.name_fr", read_only=True)
    professional_name = serializers.CharField(source="professional_profile.legal_name", read_only=True, default="")
    professional_status = serializers.CharField(source="professional_profile.verification_status", read_only=True, default="")
    is_catalog_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = CatalogSeller
        fields = (
            "id", "kind", "professional_profile", "professional_name", "professional_status", "name", "country",
            "country_name", "region", "city", "verification_status", "verification_status_label",
            "verification_reference", "is_active", "is_catalog_verified", "created_at", "updated_at",
        )
        read_only_fields = ("id", "professional_name", "professional_status", "country_name", "is_catalog_verified", "created_at", "updated_at")

    def validate(self, attrs):
        values = {field: getattr(self.instance, field) for field in (
            "kind", "professional_profile", "name", "country", "region", "city", "verification_status", "verification_reference", "is_active",
        )} if self.instance else {}
        values.update(attrs)
        if values.get("kind") == CatalogSeller.Kind.PHARMACY and values.get("professional_profile"):
            profile = values["professional_profile"]
            values["name"] = profile.legal_name
            if profile.country_id:
                values["country"] = profile.country
            values["region"] = profile.region
            values["city"] = profile.city
            attrs.update({"name": values["name"], "country": values.get("country"), "region": values["region"], "city": values["city"]})
        candidate = CatalogSeller(**values)
        try:
            candidate.full_clean(exclude=("created_by", "updated_by"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data["updated_by"] = self.context["request"].user
        return CatalogSeller.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)


class PublicCatalogSellerSerializer(serializers.ModelSerializer):
    country = serializers.CharField(source="country.name_fr", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    verified = serializers.SerializerMethodField()

    class Meta:
        model = CatalogSeller
        fields = ("id", "kind", "kind_label", "name", "country", "region", "city", "verified")

    @extend_schema_field(serializers.BooleanField())
    def get_verified(self, instance):
        return instance.is_catalog_verified


class CatalogProductAdminSerializer(serializers.ModelSerializer):
    product_type_label = serializers.CharField(source="get_product_type_display", read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    seller_status = serializers.CharField(source="seller.verification_status", read_only=True)
    seller_is_verified = serializers.BooleanField(source="seller.is_catalog_verified", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    moderation_status_label = serializers.CharField(source="get_moderation_status_display", read_only=True)
    authorization_status_label = serializers.CharField(source="get_authorization_status_display", read_only=True)
    authorization_reviewed_by_username = serializers.CharField(source="authorization_reviewed_by.username", read_only=True, default="")
    image_url = serializers.SerializerMethodField()
    price_mga = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = CatalogProduct
        fields = (
            "id", "product_type", "product_type_label", "title", "slug", "brand", "description", "image", "image_url",
            "seller", "seller_name", "seller_status", "seller_is_verified", "price_mga", "availability", "status", "status_label",
            "moderation_status", "moderation_status_label", "submitted_for_review_at", "review_notes",
            "is_sponsored", "price_updated_at", "availability_updated_at", "updated_at",
            "active_ingredient", "dosage", "pharmaceutical_form", "packaging", "requires_prescription",
            "authorization_status", "authorization_status_label", "authorization_reference",
            "authorization_submitted_at", "authorization_verified_reference", "authorization_reviewed_by",
            "authorization_reviewed_by_username", "authorization_reviewed_at", "authorization_review_notes",
            "authorization_decision_tracked", "equipment_category", "model_name",
            "technical_specifications", "warranty",
        )
        read_only_fields = (
            "id", "slug", "product_type_label", "seller_name", "seller_status", "seller_is_verified",
            "status_label", "moderation_status", "moderation_status_label", "submitted_for_review_at",
            "review_notes", "image_url", "price_updated_at", "availability_updated_at", "updated_at",
            "authorization_status", "authorization_status_label", "authorization_reference",
            "authorization_submitted_at", "authorization_verified_reference", "authorization_reviewed_by",
            "authorization_reviewed_by_username", "authorization_reviewed_at", "authorization_review_notes",
            "authorization_decision_tracked",
        )
        extra_kwargs = {"image": {"required": False, "allow_empty_file": False}}

    def validate_image(self, image):
        return validate_product_image_file(image)

    def validate(self, attrs):
        field_names = (
            "product_type", "title", "brand", "description", "seller", "price_mga", "availability", "status", "is_sponsored",
            "active_ingredient", "dosage", "pharmaceutical_form", "packaging", "requires_prescription", "authorization_status",
            "authorization_reference", "authorization_submitted_at", "authorization_verified_reference",
            "authorization_reviewed_by", "authorization_reviewed_at", "authorization_review_notes",
            "authorization_decision_tracked", "equipment_category", "model_name", "technical_specifications", "warranty",
        )
        values = {field: getattr(self.instance, field) for field in field_names} if self.instance else {}
        values.update(attrs)
        candidate = CatalogProduct(**values)
        try:
            candidate.full_clean(exclude=("slug", "image", "created_by", "updated_by"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return CatalogProduct.objects.create(created_by=user, updated_by=user, **validated_data)

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, instance):
        if not instance.image:
            return None
        request = self.context.get("request")
        path = f"/api/v1/marketplace/admin/products/{instance.pk}/image/"
        return request.build_absolute_uri(path) if request else path


class PublicProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "alt_text", "sort_order", "is_primary", "url")

    @extend_schema_field(serializers.URLField())
    def get_url(self, instance):
        path = f"/api/v1/marketplace/public/products/{instance.product.slug}/images/{instance.pk}/"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class PublicCatalogProductSerializer(serializers.ModelSerializer):
    product_type_label = serializers.CharField(source="get_product_type_display", read_only=True)
    equipment_category_label = serializers.CharField(source="get_equipment_category_display", read_only=True)
    seller = PublicCatalogSellerSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    images = PublicProductImageSerializer(many=True, read_only=True)
    is_orderable = serializers.BooleanField(read_only=True)
    orderability_reason = serializers.CharField(read_only=True, allow_null=True)
    promotion = serializers.SerializerMethodField()
    effective_price_mga = serializers.SerializerMethodField()

    class Meta:
        model = CatalogProduct
        fields = (
            "id", "product_type", "product_type_label", "title", "slug", "brand", "description", "image_url", "images",
            "seller", "price_mga", "effective_price_mga", "promotion", "availability", "is_orderable", "orderability_reason", "is_sponsored", "price_updated_at", "availability_updated_at", "updated_at",
            "active_ingredient", "dosage", "pharmaceutical_form", "packaging", "requires_prescription",
            "equipment_category", "equipment_category_label", "model_name", "technical_specifications", "warranty",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, instance):
        if not instance.image:
            return None
        request = self.context.get("request")
        path = f"/api/v1/marketplace/public/products/{instance.slug}/image/"
        return request.build_absolute_uri(path) if request else path

    def active_promotion(self, instance):
        if not hasattr(self, "_promotion_cache"):
            self._promotion_cache = {}
        if instance.pk not in self._promotion_cache:
            promotion = public_promotion_queryset().filter(product=instance).order_by("-starts_at").first()
            self._promotion_cache[instance.pk] = promotion
        return self._promotion_cache[instance.pk]

    @extend_schema_field(PromotionPublicSerializer(allow_null=True))
    def get_promotion(self, instance):
        promotion = self.active_promotion(instance)
        if not promotion:
            return None
        return PromotionPublicSerializer(promotion, context=self.context).data

    @extend_schema_field(serializers.CharField())
    def get_effective_price_mga(self, instance):
        promotion = self.active_promotion(instance)
        price = promotion.promotional_price_mga if promotion else instance.price_mga
        return f"{price:.2f}"


class PublicCatalogListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PublicCatalogProductSerializer(many=True)


class PublicCatalogSearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    products = PublicCatalogProductSerializer(many=True)
    deferred_categories = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()


class CatalogSearchSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=120, allow_blank=True, required=False)
    city = serializers.CharField(max_length=120, allow_blank=True, required=False)
    country = serializers.IntegerField(min_value=1, required=False)
    min_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False)
    max_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False)

    def validate(self, attrs):
        if attrs.get("min_price") is not None and attrs.get("max_price") is not None and attrs["min_price"] > attrs["max_price"]:
            raise serializers.ValidationError({"max_price": "Le prix maximum doit être supérieur ou égal au minimum."})
        if attrs.get("country") and not Country.objects.filter(pk=attrs["country"], is_active=True).exists():
            raise serializers.ValidationError({"country": "Ce pays n’est pas actif."})
        return attrs


class MarketplaceAdminOptionsSerializer(serializers.Serializer):
    countries = serializers.ListField(child=serializers.DictField())
    pharmacies = serializers.ListField(child=serializers.DictField())
    accounts = serializers.ListField(child=serializers.DictField())


class PartnerSellerSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    country = serializers.CharField(source="country.name_fr", read_only=True)
    is_catalog_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = CatalogSeller
        fields = (
            "id", "kind", "kind_label", "name", "country", "region", "city",
            "verification_status", "is_active", "is_catalog_verified",
        )
        read_only_fields = fields


PARTNER_PRODUCT_WRITABLE_FIELDS = (
    "product_type",
    "title",
    "brand",
    "description",
    "price_mga",
    "availability",
    "stock_quantity",
    "active_ingredient",
    "dosage",
    "pharmaceutical_form",
    "packaging",
    "requires_prescription",
    "authorization_reference",
    "equipment_category",
    "model_name",
    "technical_specifications",
    "warranty",
)

PARTNER_SUBSTANTIVE_FIELDS = (
    "product_type",
    "title",
    "brand",
    "description",
    "price_mga",
    "active_ingredient",
    "dosage",
    "pharmaceutical_form",
    "packaging",
    "requires_prescription",
    "authorization_reference",
    "equipment_category",
    "model_name",
    "technical_specifications",
    "warranty",
)


class PartnerProductSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    product_type_label = serializers.CharField(source="get_product_type_display", read_only=True)
    moderation_status_label = serializers.CharField(source="get_moderation_status_display", read_only=True)
    authorization_status_label = serializers.CharField(source="get_authorization_status_display", read_only=True)
    image_url = serializers.SerializerMethodField()
    price_mga = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = CatalogProduct
        fields = (
            "id", "product_type", "product_type_label", "title", "slug", "brand", "description", "image_url",
            "seller", "seller_name", "price_mga", "availability", "status", "moderation_status",
            "moderation_status_label", "stock_quantity", "stock_updated_at", "price_updated_at",
            "availability_updated_at", "submitted_for_review_at", "reviewed_at", "review_notes",
            "created_at", "updated_at", "active_ingredient", "dosage", "pharmaceutical_form", "packaging",
            "requires_prescription", "authorization_status", "authorization_status_label",
            "authorization_reference", "authorization_submitted_at", "authorization_verified_reference",
            "authorization_reviewed_at", "authorization_review_notes", "authorization_decision_tracked",
            "equipment_category", "model_name", "technical_specifications", "warranty",
        )
        read_only_fields = (
            "id", "product_type_label", "slug", "image_url", "seller", "seller_name", "status",
            "moderation_status", "moderation_status_label", "stock_updated_at", "price_updated_at",
            "availability_updated_at", "submitted_for_review_at", "reviewed_at", "review_notes",
            "created_at", "updated_at", "authorization_status", "authorization_status_label",
            "authorization_submitted_at", "authorization_verified_reference", "authorization_reviewed_at",
            "authorization_review_notes", "authorization_decision_tracked",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, instance):
        if not instance.image:
            return None
        path = f"/api/v1/partner/products/{instance.pk}/image/"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def validate(self, attrs):
        if self.instance and self.instance.status == CatalogProduct.Status.ARCHIVED:
            raise serializers.ValidationError("Un produit archivé ne peut plus être modifié.")

        request = self.context["request"]
        values = {}
        if self.instance:
            for field in PARTNER_PRODUCT_WRITABLE_FIELDS:
                values[field] = getattr(self.instance, field)
            values.update({
                "seller": self.instance.seller,
                "status": self.instance.status,
                "moderation_status": self.instance.moderation_status,
                "submitted_for_review_at": self.instance.submitted_for_review_at,
                "reviewed_by": self.instance.reviewed_by,
                "reviewed_at": self.instance.reviewed_at,
                "review_notes": self.instance.review_notes,
                "authorization_status": self.instance.authorization_status,
                "authorization_verified_reference": self.instance.authorization_verified_reference,
                "authorization_reviewed_by": self.instance.authorization_reviewed_by,
                "authorization_reviewed_at": self.instance.authorization_reviewed_at,
                "authorization_review_notes": self.instance.authorization_review_notes,
                "authorization_decision_tracked": self.instance.authorization_decision_tracked,
            })
        else:
            values = {
                "seller": request.partner_seller,
                "status": CatalogProduct.Status.DRAFT,
                "moderation_status": CatalogProduct.ModerationStatus.NOT_REQUIRED,
            }
            values.update(attrs)
        values.update(attrs)
        reference_changed = bool(
            self.instance
            and "authorization_reference" in attrs
            and (attrs["authorization_reference"] or "").strip()
            != (self.instance.authorization_reference or "").strip()
        )
        if reference_changed:
            # La validation doit refléter la remise à zéro appliquée dans update().
            values.update({
                "authorization_status": CatalogProduct.AuthorizationStatus.PENDING,
                "authorization_verified_reference": "",
                "authorization_reviewed_by": None,
                "authorization_reviewed_at": None,
                "authorization_review_notes": "",
                "authorization_decision_tracked": False,
                "status": CatalogProduct.Status.DRAFT,
                "moderation_status": CatalogProduct.ModerationStatus.PENDING,
                "reviewed_by": None,
                "reviewed_at": None,
                "review_notes": "",
            })
        candidate = CatalogProduct(**values)
        try:
            candidate.full_clean(exclude=("image", "created_by", "updated_by"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        actor = request.user
        validated_data.update({
            "seller": request.partner_seller,
            "status": CatalogProduct.Status.DRAFT,
            "moderation_status": CatalogProduct.ModerationStatus.NOT_REQUIRED,
            "authorization_status": CatalogProduct.AuthorizationStatus.PENDING,
            "authorization_verified_reference": "",
            "authorization_reviewed_by": None,
            "authorization_reviewed_at": None,
            "authorization_review_notes": "",
            "authorization_decision_tracked": False,
            "created_by": actor,
            "updated_by": actor,
        })
        if (validated_data.get("authorization_reference") or "").strip():
            validated_data["authorization_submitted_at"] = timezone.now()
        with transaction.atomic():
            product = CatalogProduct.objects.create(**validated_data)
            record_price_change(product, actor=actor, reason="Prix initial")
            record_event(
                actor=actor,
                action="marketplace.product.created",
                target=product,
                request=request,
                metadata={"seller_id": request.partner_seller.pk},
            )
            if product.product_type == CatalogProduct.ProductType.MEDICINE and product.authorization_reference:
                record_event(
                    actor=actor,
                    action="marketplace.authorization.declared",
                    target=product,
                    request=request,
                    metadata={"submitted_at": product.authorization_submitted_at.isoformat()},
                )
        return product

    def update(self, instance, validated_data):
        request = self.context["request"]
        actor = request.user
        changed_fields = [
            field for field in PARTNER_SUBSTANTIVE_FIELDS
            if field in validated_data and validated_data[field] != getattr(instance, field)
        ]
        authorization_reference_changed = (
            "authorization_reference" in validated_data
            and (validated_data["authorization_reference"] or "").strip()
            != (instance.authorization_reference or "").strip()
        )
        stock_changed = (
            "stock_quantity" in validated_data and validated_data["stock_quantity"] != instance.stock_quantity
        )
        price_changed = (
            "price_mga" in validated_data and validated_data["price_mga"] != instance.price_mga
        )
        resubmitted = bool(
            changed_fields and instance.moderation_status in (
                CatalogProduct.ModerationStatus.APPROVED,
                CatalogProduct.ModerationStatus.REJECTED,
            )
        ) or authorization_reference_changed
        now = timezone.now()
        previous_stock = instance.stock_quantity
        previous_authorization_status = instance.authorization_status
        with transaction.atomic():
            if authorization_reference_changed:
                # Le partenaire declare une reference : toute decision precedente
                # est annulee et une nouvelle verification administrative est requise.
                validated_data.update({
                    "authorization_status": CatalogProduct.AuthorizationStatus.PENDING,
                    "authorization_submitted_at": now,
                    "authorization_verified_reference": "",
                    "authorization_reviewed_by": None,
                    "authorization_reviewed_at": None,
                    "authorization_review_notes": "",
                    "authorization_decision_tracked": False,
                })
            if resubmitted:
                validated_data.update({
                    "status": CatalogProduct.Status.DRAFT,
                    "moderation_status": CatalogProduct.ModerationStatus.PENDING,
                    "submitted_for_review_at": now,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "review_notes": "",
                })
            if stock_changed:
                validated_data["stock_updated_at"] = now
            validated_data["updated_by"] = actor
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.full_clean()
            instance.save()
            if price_changed:
                record_price_change(product=instance, actor=actor, reason="Modification du prix par le partenaire")
            if previous_stock is not None and previous_stock > 0 and instance.stock_quantity == 0:
                notify_stock_depleted(instance)
            record_event(
                actor=actor,
                action="marketplace.product.updated",
                target=instance,
                request=request,
                metadata={"changed_fields": changed_fields, "stock_changed": stock_changed},
            )
            if authorization_reference_changed:
                record_event(
                    actor=actor,
                    action="marketplace.authorization.declared",
                    target=instance,
                    request=request,
                    metadata={
                        "previous_status": previous_authorization_status,
                        "submitted_at": now.isoformat(),
                    },
                )
            if resubmitted:
                record_event(
                    actor=actor,
                    action="marketplace.product.resubmitted",
                    target=instance,
                    request=request,
                    metadata={"changed_fields": changed_fields},
                )
        return instance


class PartnerProductImageSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "file", "file_url", "alt_text", "sort_order", "is_primary", "created_at", "updated_at")
        read_only_fields = ("id", "file_url", "created_at", "updated_at")

    @extend_schema_field(serializers.URLField())
    def get_file_url(self, instance):
        path = f"/api/v1/partner/products/{instance.product_id}/images/{instance.pk}/file/"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def validate_file(self, value):
        return validate_product_image_file(value)

    def validate(self, attrs):
        if self.instance and self.instance.is_primary and attrs.get("is_primary") is False:
            raise serializers.ValidationError({"is_primary": "Définissez d’abord une autre image principale."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        product = self.context["product"]
        actor = request.user
        requested_primary = validated_data.pop("is_primary", False)
        had_images = product.images.exists()
        validated_data.pop("file_url", None)
        with transaction.atomic():
            image = ProductImage.objects.create(
                product=product,
                uploaded_by=actor,
                is_primary=False,
                **validated_data,
            )
            if requested_primary or not had_images:
                set_primary_product_image(image, actor=actor, request=request)
            record_event(
                actor=actor,
                action="marketplace.image.uploaded",
                target=image,
                request=request,
                metadata={"product_id": product.pk, "primary": bool(requested_primary or not had_images)},
            )
        return image

    def update(self, instance, validated_data):
        request = self.context["request"]
        actor = request.user
        old_filename = instance.file.name if "file" in validated_data else None
        old_storage = instance.file.storage if old_filename else None
        validated_data.pop("file_url", None)
        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            if validated_data.get("is_primary"):
                set_primary_product_image(instance, actor=actor, request=request)
            elif instance.is_primary and old_filename:
                sync_primary_image(instance.product, instance, actor=actor)
            record_event(
                actor=actor,
                action="marketplace.image.updated",
                target=instance,
                request=request,
                metadata={"product_id": instance.product_id},
            )
        if old_filename:
            transaction.on_commit(lambda: old_storage.delete(old_filename))
        return instance


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source="changed_by.username", read_only=True, default="")

    class Meta:
        model = ProductPriceHistory
        fields = ("id", "price_mga", "changed_at", "changed_by_username", "reason")
        read_only_fields = fields


class ProductActionRequestSerializer(serializers.Serializer):
    pass


class ModerationRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, trim_whitespace=True)


class AuthorizationReviewSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, trim_whitespace=True, required=False, allow_blank=True)


class AuthorizationQueueSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    authorization_status_label = serializers.CharField(source="get_authorization_status_display", read_only=True)

    class Meta:
        model = CatalogProduct
        fields = (
            "id", "title", "seller_name", "authorization_status", "authorization_status_label",
            "authorization_reference", "authorization_submitted_at", "updated_at",
        )
        read_only_fields = fields


class PartnerStockUpdateSerializer(serializers.Serializer):
    stock_quantity = serializers.IntegerField(allow_null=True, min_value=0, required=True)


class PartnerAvailabilityUpdateSerializer(serializers.Serializer):
    availability = serializers.ChoiceField(choices=CatalogProduct.Availability.choices, required=True)


class SellerOwnerAssignmentSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=AccountProfile.objects.all())


class SellerOwnerSerializer(serializers.ModelSerializer):
    account_username = serializers.CharField(source="account.user.username", read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)

    class Meta:
        model = SellerOwner
        fields = ("id", "account", "account_username", "seller", "seller_name", "created_at", "updated_at")
        read_only_fields = fields
