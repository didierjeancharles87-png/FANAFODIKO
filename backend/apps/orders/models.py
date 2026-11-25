import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.marketplace.models import CatalogProduct, CatalogSeller
from apps.reference.models import TimestampedModel


def generate_order_reference():
    return f"FMD-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


class OrderStatus(models.TextChoices):
    AWAITING_SELLER = "awaiting_seller", "En attente du vendeur"
    ACCEPTED = "accepted", "Acceptée"
    REJECTED = "rejected", "Refusée"
    PREPARING = "preparing", "En préparation"
    READY = "ready", "Prête pour retrait"
    COMPLETED = "completed", "Finalisée"
    CANCELLED = "cancelled", "Annulée"


class Cart(TimestampedModel):
    account = models.OneToOneField("accounts.AccountProfile", on_delete=models.CASCADE, related_name="cart")
    applied_promotion = models.ForeignKey(
        "promotions.Promotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_carts",
    )
    applied_coupon_code = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"Panier de {self.account}"


class CartItem(TimestampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(CatalogProduct, on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])

    class Meta:
        ordering = ("product__title",)
        constraints = [
            models.UniqueConstraint(fields=("cart", "product"), name="cart_one_item_per_product"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1) & models.Q(quantity__lte=99), name="cart_quantity_range"),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product_id} dans {self.cart_id}"


class Order(TimestampedModel):
    Status = OrderStatus

    customer = models.ForeignKey("accounts.AccountProfile", on_delete=models.PROTECT, related_name="orders")
    seller = models.ForeignKey(CatalogSeller, on_delete=models.PROTECT, related_name="received_orders")
    reference = models.CharField(max_length=32, unique=True, default=generate_order_reference, editable=False)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.AWAITING_SELLER, db_index=True)
    total_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    customer_note = models.TextField(max_length=1000, blank=True)
    seller_note = models.TextField(max_length=1000, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    promotion = models.ForeignKey(
        "promotions.Promotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    coupon_code = models.CharField(max_length=32, blank=True)
    subtotal_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    discount_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    delivery_address = models.ForeignKey(
        "accounts.BuyerAddress",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    delivery_recipient = models.CharField(max_length=120, blank=True)
    delivery_phone = models.CharField(max_length=20, blank=True)
    delivery_country = models.CharField(max_length=100, blank=True)
    delivery_region = models.CharField(max_length=120, blank=True)
    delivery_city = models.CharField(max_length=120, blank=True)
    delivery_neighbourhood = models.CharField(max_length=120, blank=True)
    delivery_complement = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("customer", "created_at"), name="orders_customer_created_idx"),
            models.Index(fields=("seller", "status"), name="orders_seller_status_idx"),
            models.Index(fields=("status", "created_at"), name="orders_status_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_mga__gte=0), name="orders_total_non_negative"),
        ]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(CatalogProduct, on_delete=models.PROTECT, related_name="order_items")
    title = models.CharField(max_length=180)
    unit_price_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    line_total_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    requires_prescription = models.BooleanField(default=False)
    authorization_status = models.CharField(max_length=10, blank=True)
    authorization_reference = models.CharField(max_length=160, blank=True)
    prescription_checked_by_seller = models.BooleanField(default=False)
    prescription_checked_at = models.DateTimeField(null=True, blank=True)
    promotion = models.ForeignKey(
        "promotions.Promotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    coupon_code = models.CharField(max_length=32, blank=True)
    original_unit_price_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    discount_mga = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("order", "product"), name="order_one_item_per_product"),
            models.CheckConstraint(
                condition=models.Q(unit_price_mga__gt=0)
                & models.Q(quantity__gte=1)
                & models.Q(quantity__lte=99)
                & models.Q(line_total_mga__gte=0),
                name="order_item_amounts_valid",
            ),
        ]

    def __str__(self):
        return f"{self.title} × {self.quantity}"


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_events")
    from_status = models.CharField(max_length=20, choices=OrderStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("order", "created_at"), name="orders_event_timeline_idx")]

    def __str__(self):
        return f"{self.order_id}: {self.from_status or '—'} → {self.to_status}"
