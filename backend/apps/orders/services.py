from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AccountProfile, BuyerAddress
from apps.audit.services import record_event
from apps.marketplace.models import CatalogProduct, CatalogSeller, SellerOwner
from apps.promotions.services import cart_pricing, reserve_promotion
from apps.notifications.services import (
    notify_order_created,
    notify_order_status,
    notify_stock_depleted,
)

from .models import Cart, CartItem, Order, OrderEvent, OrderItem, OrderStatus


def get_or_create_cart(account):
    cart, _ = Cart.objects.get_or_create(account=account)
    return cart


def validate_orderable_product(product, quantity=1):
    """La commandabilité est définie une seule fois, sur la fiche produit.

    Le catalogue public expose la même règle au front pour masquer le bouton de
    réservation ; le serveur reste seul juge au moment de l’ajout au panier.
    """
    errors = {}
    reason = product.orderability_reason
    if reason:
        errors["product"] = reason
    if product.stock_quantity is not None and product.stock_quantity > 0 and quantity > product.stock_quantity:
        errors["quantity"] = "La quantité demandée dépasse le stock disponible."
    if errors:
        raise ValidationError(errors)


def add_cart_item(*, account, product_id, quantity):
    product = CatalogProduct.objects.select_related("seller").filter(pk=product_id).first()
    if not product:
        raise ValidationError({"product": "Ce produit n’existe pas."})
    validate_orderable_product(product, quantity)
    with transaction.atomic():
        cart = get_or_create_cart(account)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
        if not created:
            item.quantity = quantity
            item.save(update_fields=("quantity", "updated_at"))
    return item


def update_cart_item(*, account, item_id, quantity):
    validate_quantity(quantity)
    with transaction.atomic():
        item = CartItem.objects.select_related("product__seller").filter(cart__account=account, pk=item_id).first()
        if not item:
            raise ValidationError({"detail": "Article introuvable dans votre panier."})
        validate_orderable_product(item.product, quantity)
        item.quantity = quantity
        item.save(update_fields=("quantity", "updated_at"))
    return item


def validate_quantity(quantity):
    if not isinstance(quantity, int) or quantity < 1 or quantity > 99:
        raise ValidationError({"quantity": "La quantité doit être comprise entre 1 et 99."})


def cart_summary(cart):
    items = cart.items.select_related("product", "product__seller").order_by("product__title")
    rows = []
    total = Decimal("0.00")
    for item in items:
        line_total = item.product.price_mga * item.quantity
        total += line_total
        rows.append({
            "item": item,
            "unit_price_mga": item.product.price_mga,
            "line_total_mga": line_total,
        })
    return rows, total


ALLOWED_TRANSITIONS = {
    OrderStatus.AWAITING_SELLER: {OrderStatus.ACCEPTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.PREPARING},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.COMPLETED},
    OrderStatus.REJECTED: set(),
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}

TRANSITION_TIMESTAMP_FIELDS = {
    OrderStatus.ACCEPTED: "accepted_at",
    OrderStatus.REJECTED: "rejected_at",
    OrderStatus.PREPARING: "preparing_at",
    OrderStatus.READY: "ready_at",
    OrderStatus.COMPLETED: "completed_at",
    OrderStatus.CANCELLED: "cancelled_at",
}


@transaction.atomic
def checkout(*, account, actor, customer_note="", delivery_address=None, request=None):
    """Crée une ou plusieurs réservations sans paiement, avec verrous et snapshots."""
    cart = Cart.objects.select_for_update().filter(account=account).first()
    if not cart:
        raise ValidationError({"cart": "Votre panier est vide."})
    items = list(
        CartItem.objects.select_for_update()
        .filter(cart=cart)
        .select_related("product__seller")
        .order_by("product_id")
    )
    if not items:
        raise ValidationError({"cart": "Votre panier est vide."})

    address_snapshot = {}
    if delivery_address is not None:
        address = BuyerAddress.objects.filter(pk=delivery_address.pk, account=account, is_active=True).first()
        if not address:
            raise ValidationError({"delivery_address": "Cette adresse n’appartient pas à votre compte."})
        address_snapshot = {
            "delivery_address": address,
            "delivery_recipient": address.recipient_name,
            "delivery_phone": address.phone_number,
            "delivery_country": address.country.name_fr,
            "delivery_region": address.region,
            "delivery_city": address.city,
            "delivery_neighbourhood": address.neighbourhood,
            "delivery_complement": address.complement,
        }

    product_ids = sorted({item.product_id for item in items})
    locked_products = {
        product.pk: product
        for product in CatalogProduct.objects.select_for_update()
        .filter(pk__in=product_ids)
        .select_related("seller")
        .order_by("pk")
    }
    by_seller = defaultdict(list)
    for item in items:
        product = locked_products.get(item.product_id)
        if not product:
            raise ValidationError({"product": "Un produit du panier n’existe plus."})
        validate_orderable_product(product, item.quantity)
        by_seller[product.seller_id].append((item, product))

    _, _, _, _, coupon_error = cart_pricing(cart)
    if coupon_error:
        raise ValidationError({"coupon": coupon_error})
    promotion = cart.applied_promotion
    per_unit_discount = (
        promotion.original_price_mga - promotion.promotional_price_mga if promotion else Decimal("0.00")
    )
    promotion_quantity = next((item.quantity for item in items if promotion and item.product_id == promotion.product_id), 0)

    now = timezone.now()
    orders = []
    for seller_id in sorted(by_seller):
        rows = by_seller[seller_id]
        seller = rows[0][1].seller
        subtotal = Decimal("0.00")
        order_discount = Decimal("0.00")
        for item, product in rows:
            subtotal += product.price_mga * item.quantity
            if promotion and product.pk == promotion.product_id:
                order_discount += per_unit_discount * item.quantity
        total = subtotal - order_discount

        order = Order.objects.create(
            customer=account,
            seller=seller,
            total_mga=total,
            subtotal_mga=subtotal,
            discount_mga=order_discount,
            customer_note=(customer_note or "")[:1000],
            promotion=promotion if order_discount else None,
            coupon_code=promotion.code if order_discount else "",
            **address_snapshot,
        )
        for item, product in rows:
            line_discount = per_unit_discount * item.quantity if promotion and product.pk == promotion.product_id else Decimal("0.00")
            OrderItem.objects.create(
                order=order,
                product=product,
                title=product.title,
                unit_price_mga=product.price_mga - line_discount / item.quantity,
                original_unit_price_mga=product.price_mga,
                discount_mga=line_discount,
                quantity=item.quantity,
                line_total_mga=product.price_mga * item.quantity - line_discount,
                requires_prescription=(
                    product.product_type == CatalogProduct.ProductType.MEDICINE and product.requires_prescription
                ),
                authorization_status=(
                    product.authorization_status
                    if product.product_type == CatalogProduct.ProductType.MEDICINE
                    else ""
                ),
                authorization_reference=(
                    product.authorization_reference
                    if product.product_type == CatalogProduct.ProductType.MEDICINE
                    else ""
                ),
                promotion=promotion if line_discount else None,
                coupon_code=promotion.code if line_discount else "",
                prescription_checked_by_seller=False,
            )
            previous_stock = product.stock_quantity
            product.stock_quantity -= item.quantity
            product.stock_updated_at = now
            product.save(update_fields=("stock_quantity", "stock_updated_at", "updated_at"))
            if previous_stock > 0 and product.stock_quantity == 0:
                notify_stock_depleted(product)

        if order_discount and promotion:
            reserve_promotion(
                promotion,
                order=order,
                account=account,
                quantity=promotion_quantity,
                discount_mga=order_discount,
            )

        OrderEvent.objects.create(
            order=order,
            to_status=OrderStatus.AWAITING_SELLER,
            note="Réservation créée sans paiement en ligne.",
        )
        record_event(
            actor=actor,
            action="orders.order.created",
            target=order,
            request=request,
            metadata={
                "seller_id": seller_id,
                "reference": order.reference,
                "total_mga": str(total),
                "coupon_code": order.coupon_code,
            },
        )
        notify_order_created(order, recipient=account)
        for owner in SellerOwner.objects.filter(seller=seller).select_related("account"):
            notify_order_created(order, recipient=owner.account, partner=True)
        orders.append(order)

    cart.items.all().delete()
    cart.applied_promotion = None
    cart.applied_coupon_code = ""
    cart.save(update_fields=("applied_promotion", "applied_coupon_code", "updated_at"))
    return orders


@transaction.atomic
def transition_order(
    order,
    *,
    to_status,
    actor,
    request=None,
    note="",
    reason="",
    prescription_checked=False,
):
    """Applique une transition autorisée et journalise systématiquement l'événement."""
    locked = Order.objects.select_for_update().select_related("seller").get(pk=order.pk)
    if to_status not in ALLOWED_TRANSITIONS.get(locked.status, set()):
        raise ValidationError({"status": f"Transition interdite : {locked.status} → {to_status}."})

    now = timezone.now()
    previous_status = locked.status
    if to_status == OrderStatus.REJECTED:
        clean_reason = (reason or "").strip()
        if not clean_reason:
            raise ValidationError({"reason": "Le motif du refus est obligatoire."})
        locked.rejection_reason = clean_reason[:500]

    if prescription_checked:
        if locked.seller.kind != CatalogSeller.Kind.PHARMACY:
            raise ValidationError({"prescription_checked": "Seul un pharmacien partenaire peut vérifier une ordonnance."})
        locked.items.filter(requires_prescription=True).update(
            prescription_checked_by_seller=True,
            prescription_checked_at=now,
        )

    if to_status == OrderStatus.COMPLETED and locked.items.filter(
        requires_prescription=True, prescription_checked_by_seller=False
    ).exists():
        raise ValidationError({"status": "Une ordonnance requise doit être vérifiée par le pharmacien avant finalisation."})

    timestamp_field = TRANSITION_TIMESTAMP_FIELDS.get(to_status)
    if timestamp_field:
        setattr(locked, timestamp_field, now)
    locked.status = to_status
    locked.save()

    OrderEvent.objects.create(
        order=locked,
        actor=actor,
        from_status=previous_status,
        to_status=to_status,
        note=(note or reason or "")[:500],
    )
    record_event(
        actor=actor,
        action="orders.order.status_changed",
        target=locked,
        request=request,
        metadata={
            "reference": locked.reference,
            "from_status": previous_status,
            "to_status": to_status,
            "prescription_checked": bool(prescription_checked),
        },
    )

    notify_order_status(locked, to_status, recipient=locked.customer)
    if to_status == OrderStatus.CANCELLED:
        for owner in SellerOwner.objects.filter(seller=locked.seller).select_related("account"):
            notify_order_status(locked, to_status, recipient=owner.account, partner=True)
    return locked
