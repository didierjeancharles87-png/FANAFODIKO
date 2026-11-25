from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import AccountProfile, ProfessionalVerificationRequest


class ProfessionalVerificationRequestSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ProfessionalVerificationRequest
        fields = ("id", "user_id", "user_email", "category", "organization_name", "license_number", "country", "status", "created_at", "reviewed_at", "review_notes")
        read_only_fields = ("id", "status", "created_at", "reviewed_at", "review_notes")

    def validate_license_number(self, value):
        cleaned = value.strip()
        if len(cleaned) > 80:
            raise serializers.ValidationError("Le numéro d’autorisation ne peut pas dépasser 80 caractères.")
        return cleaned

    def validate_country(self, country):
        if not country.is_active:
            raise serializers.ValidationError("Ce pays n’est pas ouvert aux nouvelles inscriptions.")
        return country

    def validate_organization_name(self, value):
        cleaned = " ".join(value.split())
        if not cleaned:
            raise serializers.ValidationError("Le nom de l’établissement ou du professionnel est obligatoire.")
        return cleaned

    def validate(self, attrs):
        user = self.context["request"].user
        if ProfessionalVerificationRequest.objects.filter(user=user, status=ProfessionalVerificationRequest.Status.PENDING).exists():
            raise serializers.ValidationError({"non_field_errors": ["Une demande de validation est déjà en attente."]})
        if attrs.get("license_number", "").strip() and ProfessionalVerificationRequest.objects.filter(
            status=ProfessionalVerificationRequest.Status.PENDING,
            category=attrs.get("category"), country=attrs.get("country"), license_number=attrs.get("license_number", "").strip()
        ).exists():
            raise serializers.ValidationError({"license_number": ["Ce numéro d’autorisation est déjà enregistré pour ce pays et cette catégorie."]})
        return attrs

    def create(self, validated_data):
        return ProfessionalVerificationRequest.objects.create(user=self.context["request"].user, **validated_data)


class AccountListSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="account_profile.status")
    roles = serializers.SlugRelatedField(source="groups", many=True, read_only=True, slug_field="name")

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "email", "first_name", "last_name", "is_active", "is_staff", "status", "roles", "date_joined")


class VerificationReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(ProfessionalVerificationRequest.Status.APPROVED, ProfessionalVerificationRequest.Status.REJECTED))
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class AdminUserMetricsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    suspended = serializers.IntegerField()
    closed = serializers.IntegerField()
    disabled = serializers.IntegerField()


class AdminVerificationMetricsSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()


class AdminDashboardSerializer(serializers.Serializer):
    users = AdminUserMetricsSerializer()
    professional_verifications = AdminVerificationMetricsSerializer()
