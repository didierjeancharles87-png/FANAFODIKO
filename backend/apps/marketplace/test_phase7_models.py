from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import AccountProfile
from apps.reference.models import Country

from .models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory, SellerOwner

User = get_user_model()


class Phase7CatalogModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get(code_alpha2="MG")
        self.user = User.objects.create_user(
            username="phase7-owner",
            email="phase7-owner@example.test",
            password="Valid-Phase7-Password-934!",
        )
        self.account, _ = AccountProfile.objects.get_or_create(user=self.user)
        self.seller = CatalogSeller.objects.create(
            kind=CatalogSeller.Kind.MEDICAL_SUPPLIER,
            name="Fournisseur Phase 7",
            country=self.country,
            city="Antananarivo",
            verification_status=CatalogSeller.VerificationStatus.VERIFIED,
            verification_reference="REF-PHASE7-001",
        )
        self.product = CatalogProduct.objects.create(
            product_type=CatalogProduct.ProductType.EQUIPMENT,
            title="Appareil Phase 7",
            seller=self.seller,
            price_mga=Decimal("15000.00"),
            availability=CatalogProduct.Availability.AVAILABLE,
            equipment_category=CatalogProduct.EquipmentCategory.DIAGNOSTIC,
        )

    def test_existing_product_keeps_neutral_phase7_defaults(self):
        self.product.refresh_from_db()
        self.assertIsNone(self.product.stock_quantity)
        self.assertIsNone(self.product.stock_updated_at)
        self.assertEqual(self.product.moderation_status, CatalogProduct.ModerationStatus.NOT_REQUIRED)
        self.assertIsNone(self.product.submitted_for_review_at)
        self.assertIsNone(self.product.reviewed_by_id)
        self.assertIsNone(self.product.reviewed_at)
        self.assertEqual(self.product.review_notes, "")
        self.assertEqual(self.product.image.name, "")

    def test_seller_owner_is_an_explicit_unique_assignment(self):
        self.assertEqual(SellerOwner.objects.count(), 0)
        assignment = SellerOwner.objects.create(account=self.account, seller=self.seller)
        self.assertEqual(assignment.account, self.account)
        self.assertEqual(assignment.seller, self.seller)

        other_user = User.objects.create_user(
            username="phase7-other-owner",
            email="phase7-other@example.test",
            password="Valid-Phase7-Password-935!",
        )
        other_account, _ = AccountProfile.objects.get_or_create(user=other_user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SellerOwner.objects.create(account=other_account, seller=self.seller)

    def test_seller_owner_clean_rejects_inactive_account(self):
        self.account.status = AccountProfile.Status.SUSPENDED
        self.account.save(update_fields=("status", "updated_at"))
        assignment = SellerOwner(account=self.account, seller=self.seller)
        with self.assertRaises(ValidationError) as caught:
            assignment.full_clean()
        self.assertIn("account", caught.exception.message_dict)

    def test_product_image_allows_one_primary_image_per_product(self):
        first = ProductImage.objects.create(product=self.product, is_primary=True, sort_order=0)
        second = ProductImage.objects.create(product=self.product, is_primary=False, sort_order=1)
        self.assertTrue(first.is_primary)
        self.assertFalse(second.is_primary)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductImage.objects.create(product=self.product, is_primary=True, sort_order=2)

    def test_price_history_contains_only_explicit_changes(self):
        self.assertEqual(ProductPriceHistory.objects.count(), 0)
        entry = ProductPriceHistory.objects.create(product=self.product, price_mga=Decimal("16000.00"), changed_by=self.user)
        self.assertEqual(ProductPriceHistory.objects.count(), 1)
        self.assertEqual(entry.price_mga, Decimal("16000.00"))
        self.assertEqual(entry.changed_by, self.user)

    def test_moderation_decision_requires_attribution_and_timestamp(self):
        self.product.moderation_status = CatalogProduct.ModerationStatus.APPROVED
        with self.assertRaises(ValidationError) as caught:
            self.product.full_clean(exclude=("slug", "image", "created_by", "updated_by"))
        self.assertIn("reviewed_at", caught.exception.message_dict)

        self.product.reviewed_by = self.user
        self.product.reviewed_at = timezone.now()
        self.product.full_clean(exclude=("slug", "image", "created_by", "updated_by"))

    def test_pending_moderation_cannot_be_published(self):
        self.product.status = CatalogProduct.Status.PUBLISHED
        self.product.moderation_status = CatalogProduct.ModerationStatus.PENDING
        self.product.submitted_for_review_at = timezone.now()
        with self.assertRaises(ValidationError) as caught:
            self.product.full_clean(exclude=("slug", "image", "created_by", "updated_by"))
        self.assertIn("moderation_status", caught.exception.message_dict)
