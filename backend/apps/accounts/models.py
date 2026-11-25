from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.reference.models import TimestampedModel
from .categories import ProfessionalCategory


class AccountProfile(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Actif"
        SUSPENDED = "suspended", "Suspendu"
        CLOSED = "closed", "Clôturé"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_profile")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")])
    country = models.ForeignKey("reference.Country", null=True, blank=True, on_delete=models.PROTECT, related_name="account_profiles")

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"Profil de {self.user}"


class BuyerAddress(TimestampedModel):
    """Coordonnées de retrait/contact d'un acheteur, sans logistique opérationnelle."""

    account = models.ForeignKey(AccountProfile, on_delete=models.CASCADE, related_name="buyer_addresses")
    label = models.CharField(max_length=60, blank=True)
    recipient_name = models.CharField(max_length=120)
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")],
    )
    country = models.ForeignKey("reference.Country", on_delete=models.PROTECT, related_name="buyer_addresses")
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    neighbourhood = models.CharField(max_length=120, blank=True)
    complement = models.CharField(max_length=500, blank=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-is_primary", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("account",),
                condition=models.Q(is_primary=True, is_active=True),
                name="buyer_one_primary_address",
            ),
            models.CheckConstraint(
                condition=models.Q(recipient_name__gt="") & models.Q(city__gt=""),
                name="buyer_address_required_fields",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_name} — {self.city}"


class ProfessionalVerificationRequest(TimestampedModel):
    class Category(models.TextChoices):
        DOCTOR = "doctor", "Médecin"
        DENTIST = "dentist", "Dentiste"
        PHARMACY = "pharmacy", "Pharmacie"
        LABORATORY = "laboratory", "Laboratoire"
        CLINIC = "clinic", "Clinique ou hôpital"
        DELIVERY_COURIER = "delivery_courier", "Livreur indépendant"
        DELIVERY_COMPANY = "delivery_company", "Société de livraison"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Refusée"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="professional_verification_requests")
    category = models.CharField(max_length=32, choices=Category.choices)
    organization_name = models.CharField(max_length=180)
    license_number = models.CharField(max_length=80, blank=True)
    country = models.ForeignKey("reference.Country", on_delete=models.PROTECT, related_name="verification_requests")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_verification_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=("user",), condition=models.Q(status="pending"), name="one_pending_prof_verification"),
            models.UniqueConstraint(
                fields=("category", "country", "license_number"),
                condition=models.Q(status="pending") & ~models.Q(license_number=""),
                name="unique_prof_license_by_country",
            ),
            models.CheckConstraint(
                condition=(models.Q(status="pending", reviewed_by__isnull=True, reviewed_at__isnull=True) | (models.Q(status__in=("approved", "rejected"), reviewed_by__isnull=False, reviewed_at__isnull=False))),
                name="verification_review_state_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.get_category_display()} — {self.organization_name} ({self.get_status_display()})"
