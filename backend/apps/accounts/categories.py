from django.db import models


class ProfessionalCategory(models.TextChoices):
    PHARMACY = "pharmacy", "Pharmacie"
    DOCTOR = "doctor", "Médecin"
    DENTIST = "dentist", "Dentiste"
    LABORATORY = "laboratory", "Laboratoire d’analyses médicales"
    DELIVERY_COURIER = "delivery_courier", "Livreur indépendant"
    DELIVERY_COMPANY = "delivery_company", "Société de livraison"


CATEGORY_DETAILS_FIELDS = {
    ProfessionalCategory.PHARMACY: {"commercial_name", "license_number", "opening_hours"},
    ProfessionalCategory.DOCTOR: {"specialty", "registration_number", "establishment_name", "availability_info"},
    ProfessionalCategory.DENTIST: {"specialty", "registration_number", "establishment_name", "availability_info"},
    ProfessionalCategory.LABORATORY: {"license_number", "services"},
    ProfessionalCategory.DELIVERY_COURIER: {"license_number", "service_areas", "delivery_types", "transport_modes"},
    ProfessionalCategory.DELIVERY_COMPANY: {"license_number", "service_areas", "delivery_types", "transport_modes"},
}
