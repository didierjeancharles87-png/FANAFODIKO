import os
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile, ProfessionalVerificationRequest
from apps.reference.models import Country, TimestampedModel
from .validators import validate_opening_hours, validate_service_areas, validate_string_list


class ProfessionalProfile(TimestampedModel):
    class VerificationStatus(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvé"
        REJECTED = "rejected", "Refusé"

    account = models.OneToOneField(AccountProfile, on_delete=models.CASCADE, related_name="professional_profile")
    category = models.CharField(max_length=32, choices=ProfessionalCategory.choices, db_index=True)
    legal_name = models.CharField(max_length=180)
    manager_name = models.CharField(max_length=180, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")])
    contact_email = models.EmailField(blank=True)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.PROTECT, related_name="professional_profiles")
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=240, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    description = models.TextField(blank=True, max_length=4000)
    verification_status = models.CharField(max_length=10, choices=VerificationStatus.choices, default=VerificationStatus.DRAFT, db_index=True)
    verification_request = models.OneToOneField(ProfessionalVerificationRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="professional_profile")

    class Meta:
        ordering = ("legal_name",)
        constraints = [
            models.CheckConstraint(condition=models.Q(latitude__isnull=True) | models.Q(latitude__gte=-90, latitude__lte=90), name="professional_latitude_range"),
            models.CheckConstraint(condition=models.Q(longitude__isnull=True) | models.Q(longitude__gte=-180, longitude__lte=180), name="professional_longitude_range"),
        ]

    @property
    def missing_information(self):
        missing = [field for field in ("legal_name", "manager_name", "contact_phone", "contact_email", "country", "region", "city", "address") if not getattr(self, field)]
        details = self.category_details
        if self.category == ProfessionalCategory.PHARMACY:
            if not details or not details.commercial_name:
                missing.append("commercial_name")
            if not details or not details.opening_hours:
                missing.append("opening_hours")
        elif self.category in (ProfessionalCategory.DOCTOR, ProfessionalCategory.DENTIST):
            if not details or not details.specialty:
                missing.append("specialty")
            if not details or not details.establishment_name:
                missing.append("establishment_name")
        elif self.category == ProfessionalCategory.LABORATORY:
            if not details or not details.services:
                missing.append("services")
        elif self.category in (ProfessionalCategory.DELIVERY_COURIER, ProfessionalCategory.DELIVERY_COMPANY):
            for field in ("service_areas", "delivery_types", "transport_modes"):
                if not details or not getattr(details, field):
                    missing.append(field)
        if not self.documents.exists():
            missing.append("supporting_document")
        return missing

    @property
    def category_details(self):
        field_name = {
            ProfessionalCategory.PHARMACY: "pharmacy_details",
            ProfessionalCategory.DOCTOR: "practitioner_details",
            ProfessionalCategory.DENTIST: "practitioner_details",
            ProfessionalCategory.LABORATORY: "laboratory_details",
            ProfessionalCategory.DELIVERY_COURIER: "delivery_details",
            ProfessionalCategory.DELIVERY_COMPANY: "delivery_details",
        }.get(self.category)
        if not field_name:
            return None
        try:
            return getattr(self, field_name)
        except (PharmacyDetails.DoesNotExist, PractitionerDetails.DoesNotExist, LaboratoryDetails.DoesNotExist, DeliveryDetails.DoesNotExist):
            return None

    @property
    def is_complete(self):
        return not self.missing_information

    def __str__(self):
        return f"{self.legal_name} — {self.get_category_display()}"


class PharmacyDetails(TimestampedModel):
    profile = models.OneToOneField(ProfessionalProfile, on_delete=models.CASCADE, related_name="pharmacy_details")
    commercial_name = models.CharField(max_length=180, blank=True)
    license_number = models.CharField(max_length=80, blank=True)
    opening_hours = models.JSONField(default=dict, blank=True, validators=[validate_opening_hours])


class PractitionerDetails(TimestampedModel):
    profile = models.OneToOneField(ProfessionalProfile, on_delete=models.CASCADE, related_name="practitioner_details")
    specialty = models.CharField(max_length=160, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    establishment_name = models.CharField(max_length=180, blank=True)
    availability_info = models.CharField(max_length=1000, blank=True)


class LaboratoryDetails(TimestampedModel):
    profile = models.OneToOneField(ProfessionalProfile, on_delete=models.CASCADE, related_name="laboratory_details")
    license_number = models.CharField(max_length=80, blank=True)
    services = models.JSONField(default=list, blank=True, validators=[validate_string_list])


class DeliveryDetails(TimestampedModel):
    profile = models.OneToOneField(ProfessionalProfile, on_delete=models.CASCADE, related_name="delivery_details")
    license_number = models.CharField(max_length=80, blank=True)
    service_areas = models.JSONField(default=list, blank=True, validators=[validate_service_areas])
    delivery_types = models.JSONField(default=list, blank=True, validators=[validate_string_list])
    transport_modes = models.JSONField(default=list, blank=True, validators=[validate_string_list])


def professional_document_upload_to(instance, filename):
    extension = os.path.splitext(filename.replace("\\", "/"))[-1].lower()
    return f"professional-documents/{instance.profile_id}/{uuid.uuid4().hex}{extension}"


class ProfessionalDocument(TimestampedModel):
    class DocumentType(models.TextChoices):
        LICENSE = "license", "Licence ou autorisation"
        DIPLOMA = "diploma", "Diplôme"
        IDENTITY = "identity", "Pièce d’identité"
        REGISTRATION = "registration", "Inscription professionnelle"
        FACILITY = "facility", "Document de l’établissement"
        OTHER = "other", "Autre justificatif"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "À examiner"
        ACCEPTED = "accepted", "Accepté"
        REJECTED = "rejected", "Refusé"

    profile = models.ForeignKey(ProfessionalProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=16, choices=DocumentType.choices)
    file = models.FileField(upload_to=professional_document_upload_to)
    original_filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=80)
    size_bytes = models.PositiveIntegerField()
    review_status = models.CharField(max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.profile.legal_name}"
