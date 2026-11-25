import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.professionals.models import ProfessionalProfile
from apps.reference.models import Country, TimestampedModel


class CatalogSeller(TimestampedModel):
    class Kind(models.TextChoices):
        PHARMACY = "pharmacy", "Pharmacie"
        MEDICAL_SUPPLIER = "medical_supplier", "Fournisseur de matériel médical"

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "À vérifier"
        VERIFIED = "verified", "Vérifié"
        REJECTED = "rejected", "Refusé"

    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    professional_profile = models.OneToOneField(
        ProfessionalProfile, null=True, blank=True, on_delete=models.PROTECT,
        related_name="marketplace_seller",
    )
    name = models.CharField(max_length=180)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="catalog_sellers")
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    verification_status = models.CharField(max_length=10, choices=VerificationStatus.choices, default=VerificationStatus.PENDING, db_index=True)
    verification_reference = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_catalog_sellers")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_catalog_sellers")

    class Meta:
        ordering = ("name",)

    def clean(self):
        errors = {}
        if self.kind == self.Kind.PHARMACY:
            if not self.professional_profile:
                errors["professional_profile"] = "Une pharmacie du catalogue doit être liée à un profil professionnel existant."
            elif self.professional_profile.category != ProfessionalCategory.PHARMACY:
                errors["professional_profile"] = "Le profil associé doit être une pharmacie."
            elif self.verification_status == self.VerificationStatus.VERIFIED and not self.professional_is_verified:
                errors["verification_status"] = "La pharmacie doit avoir un profil actif et approuvé."
        elif self.kind == self.Kind.MEDICAL_SUPPLIER:
            if self.professional_profile_id:
                errors["professional_profile"] = "Un fournisseur de matériel doit être géré comme fournisseur, sans profil pharmacie associé."
            if self.verification_status == self.VerificationStatus.VERIFIED and not self.verification_reference.strip():
                errors["verification_reference"] = "Une référence de vérification est requise pour valider ce fournisseur."
        if self.country_id and not self.country.is_active:
            errors["country"] = "Le pays du vendeur n’est pas actif."
        if errors:
            raise ValidationError(errors)

    @property
    def professional_is_verified(self):
        profile = self.professional_profile
        if not profile:
            return False
        try:
            account = profile.account
            user = account.user
            return bool(
                profile.verification_status == ProfessionalProfile.VerificationStatus.APPROVED
                and account.status == AccountProfile.Status.ACTIVE
                and user.is_active
                and user.groups.filter(name="professional_verified").exists()
            )
        except AccountProfile.DoesNotExist:
            return False

    @property
    def is_catalog_verified(self):
        if not self.is_active or self.verification_status != self.VerificationStatus.VERIFIED:
            return False
        if self.kind == self.Kind.PHARMACY:
            return self.professional_is_verified
        return bool(self.verification_reference.strip())

    def __str__(self):
        return self.name


class SellerOwner(TimestampedModel):
    account = models.OneToOneField(AccountProfile, on_delete=models.PROTECT, related_name="marketplace_seller_owner")
    seller = models.OneToOneField(CatalogSeller, on_delete=models.PROTECT, related_name="owner_assignment")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_catalog_seller_owners")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_catalog_seller_owners")

    def clean(self):
        errors = {}
        account = getattr(self, "account", None)
        seller = getattr(self, "seller", None)
        if account:
            if account.status != AccountProfile.Status.ACTIVE or not account.user.is_active:
                errors["account"] = "Le propriétaire du vendeur doit avoir un compte actif."
        if seller and seller.kind == CatalogSeller.Kind.PHARMACY:
            try:
                profile = account.professional_profile if account else None
            except ProfessionalProfile.DoesNotExist:
                profile = None
            if not profile:
                errors["account"] = "Le propriétaire d'une pharmacie doit avoir un profil professionnel."
            elif profile.category != ProfessionalCategory.PHARMACY:
                errors["account"] = "Le profil du propriétaire doit être celui d'une pharmacie."
            elif profile.verification_status != ProfessionalProfile.VerificationStatus.APPROVED:
                errors["account"] = "Le profil pharmacie du propriétaire doit être approuvé."
            elif seller.professional_profile_id != profile.pk:
                errors["seller"] = "La pharmacie attribuée doit correspondre au profil du propriétaire."
        elif seller and seller.kind == CatalogSeller.Kind.MEDICAL_SUPPLIER:
            if not seller.verification_reference.strip():
                errors["seller"] = "Un fournisseur doit conserver sa référence de vérification."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.account_id} → {self.seller_id}"


def catalog_product_upload_to(instance, filename):
    extension = os.path.splitext(filename.replace("\\", "/"))[-1].lower()
    return f"marketplace/products/{uuid.uuid4().hex}{extension}"


def product_image_upload_to(instance, filename):
    extension = os.path.splitext(filename.replace("\\", "/"))[-1].lower()
    return f"marketplace/products/{instance.product_id}/{uuid.uuid4().hex}{extension}"


class CatalogProduct(TimestampedModel):
    class ProductType(models.TextChoices):
        MEDICINE = "medicine", "Médicament"
        EQUIPMENT = "equipment", "Matériel médical"

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publié"
        ARCHIVED = "archived", "Archivé"

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        LIMITED = "limited", "Disponibilité limitée"
        UNAVAILABLE = "unavailable", "Indisponible"

    class AuthorizationStatus(models.TextChoices):
        PENDING = "pending", "À vérifier"
        VERIFIED = "verified", "AMM vérifiée"
        REJECTED = "rejected", "AMM refusée"

    class EquipmentCategory(models.TextChoices):
        DIAGNOSTIC = "diagnostic", "Diagnostic"
        MONITORING = "monitoring", "Surveillance médicale"
        MOBILITY = "mobility", "Mobilité et transfert"
        PROTECTION = "protection", "Protection"
        CONSUMABLES = "consumables", "Consommables"
        OTHER = "other", "Autre matériel médical"

    class ModerationStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Non requise"
        PENDING = "pending", "En attente de modération"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Refusée"

    product_type = models.CharField(max_length=16, choices=ProductType.choices, db_index=True)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    brand = models.CharField(max_length=160, blank=True)
    description = models.TextField(max_length=4000, blank=True)
    image = models.FileField(upload_to=catalog_product_upload_to, blank=True, validators=[FileExtensionValidator(("jpg", "jpeg", "png", "webp"))])
    seller = models.ForeignKey(CatalogSeller, on_delete=models.PROTECT, related_name="products")
    price_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    availability = models.CharField(max_length=16, choices=Availability.choices, default=Availability.UNAVAILABLE, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_sponsored = models.BooleanField(default=False)
    price_updated_at = models.DateTimeField(default=timezone.now)
    availability_updated_at = models.DateTimeField(default=timezone.now)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    stock_updated_at = models.DateTimeField(null=True, blank=True)
    moderation_status = models.CharField(max_length=16, choices=ModerationStatus.choices, default=ModerationStatus.NOT_REQUIRED, db_index=True)
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_catalog_products")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.CharField(max_length=1000, blank=True)

    # Medication fields. Prescription-required defaults to the safer display state.
    active_ingredient = models.CharField(max_length=180, blank=True)
    dosage = models.CharField(max_length=120, blank=True)
    pharmaceutical_form = models.CharField(max_length=120, blank=True)
    packaging = models.CharField(max_length=160, blank=True)
    requires_prescription = models.BooleanField(default=True)
    authorization_status = models.CharField(max_length=10, choices=AuthorizationStatus.choices, default=AuthorizationStatus.PENDING, db_index=True)
    authorization_reference = models.CharField(max_length=160, blank=True)
    # La référence déclarée par le partenaire peut changer ; la référence vérifiée
    # est un instantané figé par la décision administrative.
    authorization_submitted_at = models.DateTimeField(null=True, blank=True)
    authorization_verified_reference = models.CharField(max_length=160, blank=True)
    authorization_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="authorization_decisions",
    )
    authorization_reviewed_at = models.DateTimeField(null=True, blank=True)
    authorization_review_notes = models.CharField(max_length=500, blank=True)
    authorization_decision_tracked = models.BooleanField(default=False, db_index=True)

    # Equipment fields.
    equipment_category = models.CharField(max_length=20, choices=EquipmentCategory.choices, blank=True)
    model_name = models.CharField(max_length=160, blank=True)
    technical_specifications = models.JSONField(default=dict, blank=True)
    warranty = models.CharField(max_length=240, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_catalog_products")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_catalog_products")

    class Meta:
        ordering = ("-is_sponsored", "title")
        indexes = [
            models.Index(fields=("product_type", "status", "availability"), name="catalog_public_products_idx"),
            models.Index(fields=("seller", "status"), name="catalog_seller_products_idx"),
            models.Index(fields=("seller", "moderation_status"), name="catalog_moderation_seller_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price_mga__gt=0), name="catalog_product_price_positive"),
        ]

    @property
    def orderability_reason(self):
        """Premier motif bloquant la réservation, ou ``None`` si la fiche est commandable.

        Un stock non renseigné (``None``) n’est jamais remplacé par une valeur inventée :
        la fiche reste consultable mais n’est pas réservable.
        """
        if self.status != self.Status.PUBLISHED:
            return "Ce produit n’est pas publié."
        if self.moderation_status not in (self.ModerationStatus.NOT_REQUIRED, self.ModerationStatus.APPROVED):
            return "Ce produit n’a pas été approuvé."
        if not self.seller.is_catalog_verified:
            return "Le vendeur de ce produit n’est pas vérifié."
        if self.availability == self.Availability.UNAVAILABLE:
            return "Ce produit est indisponible."
        if self.stock_quantity is None:
            return "Le stock de ce produit n’est pas renseigné."
        if self.stock_quantity <= 0:
            return "Ce produit est en rupture de stock."
        if self.product_type == self.ProductType.MEDICINE:
            reference = (self.authorization_reference or "").strip()
            verified_reference = (self.authorization_verified_reference or "").strip()
            if self.authorization_status != self.AuthorizationStatus.VERIFIED or not verified_reference:
                return "L’AMM de ce médicament n’est pas vérifiée."
            if reference != verified_reference:
                return "La référence AMM déclarée n’est pas celle qui a été vérifiée."
            if not reference:
                return "La référence AMM de ce médicament est absente."
        return None

    @property
    def is_orderable(self):
        return self.orderability_reason is None

    def clean(self):
        errors = {}
        authorization_reference = (self.authorization_reference or "").strip()
        verified_reference = (self.authorization_verified_reference or "").strip()
        if self.product_type == self.ProductType.MEDICINE:
            if self.seller_id and self.seller.kind != CatalogSeller.Kind.PHARMACY:
                errors["seller"] = "Un médicament doit être rattaché à une pharmacie."
            for field in ("active_ingredient", "dosage", "pharmaceutical_form", "packaging"):
                if not getattr(self, field).strip():
                    errors[field] = "Ce champ est obligatoire pour une fiche médicament."
            if self.authorization_status == self.AuthorizationStatus.VERIFIED:
                if not authorization_reference:
                    errors["authorization_reference"] = "La référence AMM déclarée est absente."
                if not verified_reference or verified_reference != authorization_reference:
                    errors["authorization_status"] = "La référence vérifiée doit correspondre à la référence AMM déclarée."
                if self.authorization_decision_tracked and (
                    not self.authorization_reviewed_by_id or not self.authorization_reviewed_at
                ):
                    errors["authorization_reviewed_at"] = "Une décision AMM vérifiée doit être attribuée et horodatée."
            elif self.authorization_status == self.AuthorizationStatus.REJECTED:
                if self.authorization_decision_tracked and not self.authorization_review_notes.strip():
                    errors["authorization_review_notes"] = "Le motif du refus AMM est obligatoire."
            elif self.authorization_decision_tracked:
                errors["authorization_status"] = "Une décision AMM suivie doit être vérifiée ou refusée."
            if self.status == self.Status.PUBLISHED:
                if self.authorization_status != self.AuthorizationStatus.VERIFIED:
                    errors["authorization_status"] = "Une AMM vérifiée est requise avant publication."
                if not authorization_reference:
                    errors["authorization_reference"] = "La référence de l’AMM doit être renseignée avant publication."
                if not verified_reference or verified_reference != authorization_reference:
                    errors["authorization_status"] = "Une AMM validée par l’administration est requise avant publication."
        elif self.product_type == self.ProductType.EQUIPMENT:
            if not self.equipment_category:
                errors["equipment_category"] = "La catégorie du matériel est obligatoire."
            if not isinstance(self.technical_specifications, dict):
                errors["technical_specifications"] = "Les caractéristiques doivent être un objet de champs et valeurs."
            elif self.technical_specifications and any(
                not isinstance(key, str) or not isinstance(value, (str, int, float, bool)) or len(str(key)) > 80 or len(str(value)) > 300
                for key, value in self.technical_specifications.items()
            ):
                errors["technical_specifications"] = "Chaque caractéristique doit être une valeur simple de 300 caractères maximum."
        if self.status == self.Status.PUBLISHED and self.seller_id and not self.seller.is_catalog_verified:
            errors["seller"] = "Seul un vendeur actif et vérifié peut publier un produit."
        if self.moderation_status in (self.ModerationStatus.APPROVED, self.ModerationStatus.REJECTED):
            if not self.reviewed_by_id or not self.reviewed_at:
                errors["reviewed_at"] = "Une décision de modération doit être attribuée et horodatée."
        elif self.reviewed_by_id or self.reviewed_at:
            errors["moderation_status"] = "Seules les décisions approuvée ou refusée peuvent être attribuées et horodatées."
        if self.moderation_status == self.ModerationStatus.PENDING and not self.submitted_for_review_at:
            errors["submitted_for_review_at"] = "Une soumission doit être horodatée."
        if self.status == self.Status.PUBLISHED and self.moderation_status not in (self.ModerationStatus.NOT_REQUIRED, self.ModerationStatus.APPROVED):
            errors["moderation_status"] = "Un produit publié doit être approuvé ou ne pas nécessiter de modération."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        now = timezone.now()
        update_fields = kwargs.get("update_fields")
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).only("price_mga", "availability").first()
            if previous:
                if previous.price_mga != self.price_mga:
                    self.price_updated_at = now
                if previous.availability != self.availability:
                    self.availability_updated_at = now
        else:
            self.price_updated_at = self.price_updated_at or now
            self.availability_updated_at = self.availability_updated_at or now
        if not self.slug:
            self.slug = f"{slugify(self.title)[:190] or 'produit'}-{uuid.uuid4().hex[:8]}"
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update(("price_updated_at", "availability_updated_at", "updated_at"))
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ProductImage(TimestampedModel):
    product = models.ForeignKey(CatalogProduct, on_delete=models.CASCADE, related_name="images")
    file = models.FileField(upload_to=product_image_upload_to, validators=[FileExtensionValidator(("jpg", "jpeg", "png", "webp"))])
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_catalog_product_images")

    class Meta:
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("product",), condition=models.Q(is_primary=True), name="catalog_one_primary_product_image"),
        ]

    def __str__(self):
        return f"Image {self.pk} — {self.product_id}"


class ProductPriceHistory(models.Model):
    product = models.ForeignKey(CatalogProduct, on_delete=models.CASCADE, related_name="price_history")
    price_mga = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="catalog_price_changes")
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("-changed_at",)
        indexes = [models.Index(fields=("product", "changed_at"), name="catalog_price_history_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(price_mga__gt=0), name="catalog_price_history_positive"),
        ]

    def __str__(self):
        return f"{self.product_id}: {self.price_mga} MGA le {self.changed_at:%Y-%m-%d}"
