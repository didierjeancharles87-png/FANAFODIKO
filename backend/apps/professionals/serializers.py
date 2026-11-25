import os
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.accounts.categories import CATEGORY_DETAILS_FIELDS, ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.reference.models import Country
from .models import DeliveryDetails, LaboratoryDetails, PharmacyDetails, PractitionerDetails, ProfessionalDocument, ProfessionalProfile


DETAIL_MODELS = {
    ProfessionalCategory.PHARMACY: PharmacyDetails,
    ProfessionalCategory.DOCTOR: PractitionerDetails,
    ProfessionalCategory.DENTIST: PractitionerDetails,
    ProfessionalCategory.LABORATORY: LaboratoryDetails,
    ProfessionalCategory.DELIVERY_COURIER: DeliveryDetails,
    ProfessionalCategory.DELIVERY_COMPANY: DeliveryDetails,
}


class ProfessionalProfileSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    account_status = serializers.CharField(source="account.status", read_only=True)
    details = serializers.JSONField(required=False)
    missing_information = serializers.ListField(child=serializers.CharField(), read_only=True)
    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProfessionalProfile
        fields = (
            "id", "category", "category_label", "legal_name", "manager_name", "contact_phone", "contact_email",
            "country", "region", "city", "address", "latitude", "longitude", "description", "details",
            "account_status", "verification_status", "is_complete", "missing_information", "created_at", "updated_at",
        )
        read_only_fields = ("id", "category", "category_label", "account_status", "verification_status", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        details = instance.category_details
        if details is None:
            data["details"] = {}
        else:
            model_fields = CATEGORY_DETAILS_FIELDS[instance.category]
            data["details"] = {name: getattr(details, name) for name in model_fields}
        return data

    def validate_contact_phone(self, value):
        if value:
            from django.core.validators import RegexValidator
            from django.core.exceptions import ValidationError

            try:
                RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")(value)
            except ValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
        return value.strip()

    def validate_country(self, country):
        if not country.is_active:
            raise serializers.ValidationError("Ce pays n’est pas actif.")
        return country

    def validate_details(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Les informations spécifiques doivent être un objet.")
        profile = self.instance
        category = profile.category if profile else self.context.get("category")
        allowed = CATEGORY_DETAILS_FIELDS.get(category, set())
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError({"unknown_fields": sorted(unknown)})
        detail_model = DETAIL_MODELS.get(category)
        if detail_model:
            candidate = detail_model(profile=profile, **value)
            try:
                candidate.full_clean(exclude=("profile",))
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        return value

    def update(self, instance, validated_data):
        details_data = validated_data.pop("details", None)
        if instance.verification_status == ProfessionalProfile.VerificationStatus.PENDING:
            raise serializers.ValidationError("Le profil ne peut pas être modifié pendant son examen administratif.")
        details_changed = False
        if details_data is not None:
            existing_details = instance.category_details
            details_changed = existing_details is None or any(getattr(existing_details, field) != value for field, value in details_data.items())
        changed = any(getattr(instance, field) != value for field, value in validated_data.items()) or details_changed
        if changed and instance.verification_status in (ProfessionalProfile.VerificationStatus.APPROVED, ProfessionalProfile.VerificationStatus.REJECTED):
            instance.verification_status = ProfessionalProfile.VerificationStatus.DRAFT
            instance.verification_request = None
            from django.contrib.auth.models import Group

            verified_role = Group.objects.filter(name="professional_verified").first()
            if verified_role:
                instance.account.user.groups.remove(verified_role)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if details_data is not None:
            detail_model = DETAIL_MODELS[instance.category]
            detail_model.objects.update_or_create(profile=instance, defaults=details_data)
        return instance


class ProfessionalCategorySerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class ProfessionalDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ProfessionalDocument
        fields = ("id", "document_type", "original_filename", "content_type", "size_bytes", "review_status", "download_url", "created_at")
        read_only_fields = fields

    @extend_schema_field(serializers.URLField())
    def get_download_url(self, obj):
        return f"/api/v1/professionals/me/documents/{obj.pk}/download/"


class ProfessionalDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=ProfessionalDocument.DocumentType.choices)
    file = serializers.FileField(write_only=True)

    MAX_SIZE = 10 * 1024 * 1024
    SIGNATURES = {
        "application/pdf": (".pdf", b"%PDF-"),
        "image/jpeg": ((".jpg", ".jpeg"), b"\xff\xd8\xff"),
        "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    }

    def create(self, validated_data):
        return ProfessionalDocument.objects.create(**validated_data)

    def validate_file(self, uploaded):
        if uploaded.size <= 0 or uploaded.size > self.MAX_SIZE:
            raise serializers.ValidationError("Le fichier doit peser entre 1 octet et 10 Mo.")
        safe_name = PurePosixPath(uploaded.name.replace("\\", "/")).name
        if len(safe_name) > 200:
            raise serializers.ValidationError("Le nom de fichier ne peut pas dépasser 200 caractères.")
        extension = os.path.splitext(safe_name)[1].lower()
        head = uploaded.read(16)
        uploaded.seek(0)
        detected = next((mime for mime, (_, signature) in self.SIGNATURES.items() if head.startswith(signature)), None)
        if not detected:
            raise serializers.ValidationError("Format refusé. Utilisez un PDF, un JPEG ou un PNG valide.")
        extensions = self.SIGNATURES[detected][0]
        if extension not in (extensions if isinstance(extensions, tuple) else (extensions,)):
            raise serializers.ValidationError("L’extension ne correspond pas au contenu du fichier.")
        if uploaded.content_type not in (detected, "application/octet-stream"):
            raise serializers.ValidationError("Le type MIME déclaré ne correspond pas au fichier.")
        uploaded._fanafodiko_detected_type = detected
        uploaded._fanafodiko_safe_name = safe_name
        return uploaded


class AdminProfessionalProfileSerializer(ProfessionalProfileSerializer):
    user_id = serializers.IntegerField(source="account.user_id", read_only=True)
    user_email = serializers.EmailField(source="account.user.email", read_only=True)

    class Meta(ProfessionalProfileSerializer.Meta):
        fields = ProfessionalProfileSerializer.Meta.fields + ("user_id", "user_email")


class AdminProfessionalDocumentSerializer(ProfessionalDocumentSerializer):
    profile_id = serializers.IntegerField(read_only=True)
    profile_name = serializers.CharField(source="profile.legal_name", read_only=True)
    category = serializers.CharField(source="profile.category", read_only=True)

    class Meta(ProfessionalDocumentSerializer.Meta):
        fields = ProfessionalDocumentSerializer.Meta.fields + ("profile_id", "profile_name", "category")

    @extend_schema_field(serializers.URLField())
    def get_download_url(self, obj):
        return f"/api/v1/professionals/admin/documents/{obj.pk}/download/"


class ProfessionalAccountStatusSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
