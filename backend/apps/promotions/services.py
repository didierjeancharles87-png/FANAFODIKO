from decimal import Decimal, ROUND_HALF_UP
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.marketplace.models import CatalogProduct

from .models import DiscountType, Promotion, PromotionStatus, Redemption


CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{4,32}$")


def derive_promotion_prices(*, original_price, discount_type, discount_value):
    """Dérive les deux prix côté serveur ; aucun prix n'est accepté du client."""
    original = Decimal(original_price).quantize(Decimal("0.01"))
    value = Decimal(discount_value)
    if original <= 0 or value <= 0:
        raise ValidationError({"discount_value": "La réduction doit être positive."})
    if discount_type == DiscountType.PERCENT:
        if value > Decimal("90"):
            raise ValidationError({"discount_value": "La réduction ne peut pas dépasser 90 %."})
        promotional = (original * (Decimal("1") - value / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        if value > original:
            raise ValidationError({"discount_value": "La réduction fixe ne peut pas dépasser le prix du produit."})
        promotional = (original - value).quantize(Decimal("0.01"))
    if promotional <= 0:
        raise ValidationError({"discount_value": "La réduction laisse un prix promotionnel invalide."})
    return original, promotional


def normalize_coupon_code(value):
    code = (value or "").strip().upper().replace(" ", "")
    if not CODE_PATTERN.fullmatch(code):
        raise ValidationError({"code": "Le code coupon doit contenir 4 à 32 lettres, chiffres, tirets ou underscore."})
    return code


def promotion_product_is_public(product):
    """Réplique les règles publiques sans jamais les assouplir pour une promotion."""
    if product.status != CatalogProduct.Status.PUBLISHED:
        return False
    if product.moderation_status not in (
        CatalogProduct.ModerationStatus.NOT_REQUIRED,
        CatalogProduct.ModerationStatus.APPROVED,
    ):
        return False
    if not product.seller.is_catalog_verified:
        return False
    if product.product_type == CatalogProduct.ProductType.MEDICINE:
        reference = (product.authorization_reference or "").strip()
        verified_reference = (product.authorization_verified_reference or "").strip()
        return bool(
            product.authorization_status == CatalogProduct.AuthorizationStatus.VERIFIED
            and reference
            and verified_reference == reference
        )
    return product.product_type == CatalogProduct.ProductType.EQUIPMENT


def public_promotion_queryset():
    now = timezone.now()
    from apps.marketplace.views import verified_seller_filter

    return (
        Promotion.objects.select_related("product", "product__seller", "seller")
        .filter(
            status=PromotionStatus.ACTIVE,
            starts_at__lte=now,
            ends_at__gte=now,
            product__status=CatalogProduct.Status.PUBLISHED,
            product__moderation_status__in=(
                CatalogProduct.ModerationStatus.NOT_REQUIRED,
                CatalogProduct.ModerationStatus.APPROVED,
            ),
        )
        .filter(verified_seller_filter())
        .filter(
            Q(product__product_type=CatalogProduct.ProductType.EQUIPMENT)
            | Q(
                product__product_type=CatalogProduct.ProductType.MEDICINE,
                product__authorization_status=CatalogProduct.AuthorizationStatus.VERIFIED,
                product__authorization_reference__gt="",
                product__authorization_verified_reference=F("product__authorization_reference"),
            )
        )
        .distinct()
        .order_by("-starts_at", "code")
    )


def promotion_usage(promotion):
    return Redemption.objects.filter(promotion=promotion).aggregate(
        quantity=Sum("quantity", default=0),
        discount=Sum("discount_mga", default=Decimal("0.00")),
    )


def validate_promotion_available(promotion, *, quantity=1, cart=None):
    errors = {}
    if promotion.status != PromotionStatus.ACTIVE:
        errors["code"] = "Cette promotion n’est pas active."
    elif promotion.is_expired:
        errors["code"] = "Cette promotion est expirée."
    elif not promotion.is_time_valid:
        errors["code"] = "Cette promotion n’est pas encore débutée."
    if not promotion_product_is_public(promotion.product):
        errors["code"] = "Le produit de cette promotion n’est pas disponible publiquement."
    if promotion.product.price_mga != promotion.original_price_mga:
        errors["code"] = "Le prix du produit a changé ; ce coupon n’est plus applicable."
    if promotion.max_redemptions is not None:
        used = promotion_usage(promotion)["quantity"] or 0
        if used + quantity > promotion.max_redemptions:
            errors["code"] = "La quantité prévue pour cette promotion est épuisée."
    if cart is not None:
        item = cart.items.filter(product=promotion.product).first()
        if not item:
            errors["code"] = "Ajoutez le produit concerné à votre panier pour utiliser ce coupon."
        elif quantity and item.quantity != quantity:
            errors["code"] = "La quantité du produit concerné a changé dans votre panier."
    if errors:
        raise ValidationError(errors)


def apply_coupon_to_cart(cart, code):
    normalized = normalize_coupon_code(code)
    promotion = Promotion.objects.filter(code=normalized).first()
    if not promotion:
        raise ValidationError({"code": "Ce code coupon est invalide."})
    with transaction.atomic():
        locked_cart = type(cart).objects.select_for_update().get(pk=cart.pk)
        locked_promotion = Promotion.objects.select_for_update().get(pk=promotion.pk)
        item = locked_cart.items.filter(product=locked_promotion.product).first()
        if not item:
            raise ValidationError({"code": "Ajoutez le produit concerné à votre panier pour utiliser ce coupon."})
        validate_promotion_available(locked_promotion, quantity=item.quantity)
        locked_cart.applied_promotion = locked_promotion
        locked_cart.applied_coupon_code = locked_promotion.code
        locked_cart.save(update_fields=("applied_promotion", "applied_coupon_code", "updated_at"))
    return locked_promotion


def clear_coupon_from_cart(cart):
    with transaction.atomic():
        locked_cart = type(cart).objects.select_for_update().get(pk=cart.pk)
        locked_cart.applied_promotion = None
        locked_cart.applied_coupon_code = ""
        locked_cart.save(update_fields=("applied_promotion", "applied_coupon_code", "updated_at"))
    return locked_cart


def cart_pricing(cart):
    """Calcule intégralement les montants côté serveur, coupons compris."""
    items = list(cart.items.select_related("product").order_by("product__title"))
    rows = []
    subtotal = Decimal("0.00")
    for item in items:
        line_total = item.product.price_mga * item.quantity
        subtotal += line_total
        rows.append({"item": item, "unit_price_mga": item.product.price_mga, "line_total_mga": line_total})

    discount = Decimal("0.00")
    coupon_error = None
    promotion = cart.applied_promotion
    if promotion:
        matching = next((row for row in rows if row["item"].product_id == promotion.product_id), None)
        if not matching:
            coupon_error = "Le produit de ce coupon n’est plus dans votre panier."
        else:
            try:
                validate_promotion_available(promotion, quantity=matching["item"].quantity)
            except ValidationError as exc:
                coupon_error = exc.messages[0] if exc.messages else "Ce coupon n’est plus valable."
            else:
                discount = (promotion.original_price_mga - promotion.promotional_price_mga) * matching["item"].quantity
    return rows, subtotal, discount, subtotal - discount, coupon_error


def reserve_promotion(promotion, *, order, account, quantity, discount_mga):
    """Vérifie le quota sous verrou puis comptabilise l'utilisation du coupon."""
    locked = Promotion.objects.select_for_update().get(pk=promotion.pk)
    validate_promotion_available(locked, quantity=quantity)
    usage = promotion_usage(locked)["quantity"] or 0
    if locked.max_redemptions is not None and usage + quantity > locked.max_redemptions:
        raise ValidationError({"code": "La quantité prévue pour cette promotion est épuisée."})
    redemption = Redemption.objects.create(
        promotion=locked,
        order_id=order.pk,
        order_reference=order.reference,
        account=account,
        coupon_code=locked.code,
        quantity=quantity,
        discount_mga=discount_mga,
    )
    Promotion.objects.filter(pk=locked.pk).update(redemption_count=F("redemption_count") + quantity)
    return redemption


def promotion_results(promotion):
    usage = promotion_usage(promotion)
    return {
        "redemption_count": promotion.redemption_count,
        "quantity_used": int(usage["quantity"] or 0),
        "total_discount_mga": f"{usage['discount'] or Decimal('0.00'):.2f}",
        "remaining_quantity": promotion.remaining_quantity,
    }


def review_promotion(promotion, *, approve, reason="", actor=None, reviewed_at=None):
    if promotion.status != PromotionStatus.PENDING:
        raise ValidationError({"status": "Cette promotion n’est plus en attente de validation."})
    clean_reason = (reason or "").strip()
    if not approve and not clean_reason:
        raise ValidationError({"review_notes": "Le motif du refus est obligatoire."})
    promotion.status = PromotionStatus.APPROVED if approve else PromotionStatus.REJECTED
    promotion.review_notes = clean_reason[:500]
    promotion.reviewed_by = actor
    promotion.reviewed_at = reviewed_at or timezone.now()
    promotion.updated_by = actor
    promotion.save(update_fields=("status", "review_notes", "reviewed_by", "reviewed_at", "updated_by", "updated_at"))
    return promotion


def activate_promotion(promotion, *, actor=None):
    if promotion.status not in (PromotionStatus.APPROVED, PromotionStatus.PAUSED):
        raise ValidationError({"status": "Seule une promotion validée ou désactivée peut être activée."})
    if promotion.is_expired:
        raise ValidationError({"ends_at": "Cette promotion est expirée."})
    if not promotion_product_is_public(promotion.product):
        raise ValidationError({"product": "Le produit de cette promotion n’est pas publié et approuvé."})
    promotion.status = PromotionStatus.ACTIVE
    promotion.updated_by = actor
    promotion.save(update_fields=("status", "updated_by", "updated_at"))
    return promotion


def deactivate_promotion(promotion, *, actor=None):
    if promotion.status != PromotionStatus.ACTIVE:
        raise ValidationError({"status": "Seule une promotion active peut être désactivée."})
    promotion.status = PromotionStatus.PAUSED
    promotion.updated_by = actor
    promotion.save(update_fields=("status", "updated_by", "updated_at"))
    return promotion


def request_promotion_removal(promotion, *, actor=None):
    if promotion.status in (PromotionStatus.REMOVAL_REQUESTED, PromotionStatus.ARCHIVED):
        raise ValidationError({"status": "Cette promotion est déjà en demande de suppression ou archivée."})
    promotion.status = PromotionStatus.REMOVAL_REQUESTED
    promotion.updated_by = actor
    promotion.save(update_fields=("status", "updated_by", "updated_at"))
    return promotion


def archive_promotion(promotion, *, actor=None):
    if promotion.status != PromotionStatus.REMOVAL_REQUESTED:
        raise ValidationError({"status": "Seules les promotions dont la suppression est demandée peuvent être archivées."})
    promotion.status = PromotionStatus.ARCHIVED
    promotion.updated_by = actor
    promotion.save(update_fields=("status", "updated_by", "updated_at"))
    return promotion
