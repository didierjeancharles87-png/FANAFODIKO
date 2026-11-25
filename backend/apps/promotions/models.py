from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.marketplace.models import CatalogProduct, CatalogSeller
from apps.reference.models import TimestampedModel


class PromotionStatus(models.TextChoices):
    PENDING = "pending", "En attente de validation"
    APPROVED = "approved", "Validée"
    REJECTED = "rejected", "Refusée"
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Désactivée"
    REMOVAL_REQUESTED = "removal_requested", "Suppression demandée"
    ARCHIVED = "archived", "Archivée"


class DiscountType(models.TextChoices):
    PERCENT = "percent", "Pourcentage"
    FIXED = "fixed", "Montant fixe"


class Promotion(TimestampedModel):
    """Promotion d'un produit, toujours modérée avant toute visibilité publique."""

    seller = models.ForeignKey(CatalogSeller, on_delete=models.PROTECT, related_name="promotions")
    product = models.ForeignKey(CatalogProduct, on_delete=models.PROTECT, related_name="promotions")
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=120)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices, db_index=True)
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    original_price_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    promotional_price_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    redemption_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=PromotionStatus.choices,
        default=PromotionStatus.PENDING,
        db_index=True,
    )
    review_notes = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_promotions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_promotions",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_promotions",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("seller", "status"), name="promotions_seller_status_idx"),
            models.Index(fields=("status", "starts_at", "ends_at"), name="promotions_public_window_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("product",),
                condition=models.Q(status=PromotionStatus.ACTIVE),
                name="promotions_one_active_per_product",
            ),
            models.CheckConstraint(condition=models.Q(discount_value__gt=0), name="promotions_discount_positive"),
            models.CheckConstraint(condition=models.Q(promotional_price_mga__lte=models.F("original_price_mga")), name="promotions_price_coherent"),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="promotions_window_coherent"),
            models.CheckConstraint(condition=models.Q(redemption_count__gte=0), name="promotions_redemption_non_negative"),
            models.CheckConstraint(
                condition=~models.Q(status__in=(
                    PromotionStatus.APPROVED,
                    PromotionStatus.REJECTED,
                    PromotionStatus.ACTIVE,
                    PromotionStatus.PAUSED,
                    PromotionStatus.REMOVAL_REQUESTED,
                    PromotionStatus.ARCHIVED,
                )) | (models.Q(reviewed_by__isnull=False) & models.Q(reviewed_at__isnull=False)),
                name="promotions_review_attributed",
            ),
        ]

    def clean(self):
        errors = {}
        if self.product_id and self.seller_id and self.product.seller_id != self.seller_id:
            errors["product"] = "Ce produit n’appartient pas au vendeur de la promotion."
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La date de fin doit être postérieure à la date de début."
        if self.discount_type == DiscountType.PERCENT and not Decimal("0") < self.discount_value <= Decimal("90"):
            errors["discount_value"] = "La réduction en pourcentage doit être comprise entre 0 et 90 %."
        if self.discount_type == DiscountType.FIXED and self.discount_value > self.original_price_mga:
            errors["discount_value"] = "La réduction fixe ne peut pas dépasser le prix initial."
        expected = self.expected_promotional_price()
        if expected is not None and abs(expected - self.promotional_price_mga) > Decimal("0.01"):
            errors["promotional_price_mga"] = f"Le prix promotionnel attendu est {expected:.2f} Ar."
        if self.promotional_price_mga and self.promotional_price_mga > self.original_price_mga:
            errors["promotional_price_mga"] = "Le prix promotionnel ne peut pas dépasser le prix initial."
        if self.status in (PromotionStatus.REJECTED,) and not self.review_notes.strip():
            errors["review_notes"] = "Le motif du refus est obligatoire."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def expected_promotional_price(self):
        if not self.original_price_mga or not self.discount_value:
            return None
        if self.discount_type == DiscountType.PERCENT:
            factor = Decimal("1") - self.discount_value / Decimal("100")
            return (self.original_price_mga * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return (self.original_price_mga - self.discount_value).quantize(Decimal("0.01"))

    @property
    def is_time_valid(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    @property
    def is_expired(self):
        return timezone.now() > self.ends_at

    @property
    def remaining_quantity(self):
        if self.max_redemptions is None:
            return None
        return max(0, self.max_redemptions - self.redemption_count)

    @property
    def discount_label(self):
        value = f"{self.discount_value:.2f}".rstrip("0").rstrip(".")
        if self.discount_type == DiscountType.PERCENT:
            return f"-{value} %"
        return f"-{value} Ar"

    def __str__(self):
        return f"{self.code} — {self.title}"


class Redemption(models.Model):
    """Utilisation atomique d'un coupon, conservée même après archivage."""

    promotion = models.ForeignKey(Promotion, on_delete=models.PROTECT, related_name="redemptions")
    order_id = models.BigIntegerField(db_index=True)
    order_reference = models.CharField(max_length=32, blank=True)
    account = models.ForeignKey("accounts.AccountProfile", on_delete=models.PROTECT, related_name="promotion_redemptions")
    coupon_code = models.CharField(max_length=32)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    discount_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("promotion", "created_at"), name="promotions_redemption_idx")]

    def __str__(self):
        return f"{self.coupon_code} × {self.quantity}"
