from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import AccountProfile
from apps.marketplace.models import CatalogProduct, CatalogSeller
from apps.reference.models import Country

from .models import Cart, CartItem, Order, OrderEvent, OrderItem, OrderStatus

User = get_user_model()


class Phase7OrderModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        self.user = User.objects.create_user(
            username="phase7-customer",
            email="phase7-customer@example.test",
            password="Valid-Phase7-Password-936!",
        )
        self.account, _ = AccountProfile.objects.get_or_create(user=self.user)
        self.seller = CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name="Fournisseur commandes Phase 7",
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
            verification_reference="REF-PHASE7-ORDER",
        )
        self.product = CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title="Matériel commandable",
            seller=self.seller,
            price_mga=Decimal("12000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
            stock_quantity=10,
            moderation_status=CatalogProduct.ModerationStatus.APPROVED,
        )
        self.cart = Cart.objects.create(account=self.account)
        self.order = Order.objects.create(customer=self.account, seller=self.seller, total_mga=Decimal("24000.00"))

    def test_cart_and_cart_item_are_unique_per_owner_and_product(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(account=self.account)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    def test_cart_item_quantity_is_between_one_and_ninety_nine(self):
        with self.assertRaises(ValidationError):
            CartItem(cart=self.cart, product=self.product, quantity=0).full_clean()
        with self.assertRaises(ValidationError):
            CartItem(cart=self.cart, product=self.product, quantity=100).full_clean()

    def test_order_starts_as_reservation_without_payment_fields(self):
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.AWAITING_SELLER)
        self.assertTrue(self.order.reference.startswith("FMD-"))
        for field in ("accepted_at", "rejected_at", "preparing_at", "ready_at", "completed_at", "cancelled_at"):
            self.assertIsNone(getattr(self.order, field))
        field_names = {field.name for field in Order._meta.get_fields()}
        self.assertFalse(any("payment" in name for name in field_names))

    def test_order_item_snapshots_price_and_prescription_state(self):
        item = OrderItem(
            order=self.order,
            product=self.product,
            title=self.product.title,
            unit_price_mga=Decimal("12000.00"),
            quantity=2,
            line_total_mga=Decimal("24000.00"),
            requires_prescription=True,
        )
        item.full_clean()
        self.assertFalse(item.prescription_checked_by_seller)
        self.assertIsNone(item.prescription_checked_at)

    def test_order_event_records_transition(self):
        event = OrderEvent.objects.create(
            order=self.order,
            actor=self.user,
            from_status=OrderStatus.AWAITING_SELLER,
            to_status=OrderStatus.ACCEPTED,
            note="Acceptation de test",
        )
        self.assertEqual(event.order, self.order)
        self.assertEqual(event.to_status, OrderStatus.ACCEPTED)
        self.assertEqual(event.actor, self.user)

    def test_order_total_cannot_be_negative(self):
        order = Order(customer=self.account, seller=self.seller, total_mga=Decimal("-1.00"))
        with self.assertRaises(ValidationError):
            order.full_clean()
