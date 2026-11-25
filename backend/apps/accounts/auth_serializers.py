from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.audit.services import record_event
from apps.professionals.models import ProfessionalProfile
from .categories import ProfessionalCategory


User = get_user_model()


class ProfessionalRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8, max_length=128)
    category = serializers.ChoiceField(choices=ProfessionalCategory.choices)
    legal_name = serializers.CharField(max_length=180, trim_whitespace=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return value

    def validate_contact_phone(self, value):
        from django.core.validators import RegexValidator
        from django.core.exceptions import ValidationError

        if not value:
            return value
        try:
            RegexValidator(r"^\+?[0-9 ()-]{6,20}$")(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value.strip()

    def validate(self, attrs):
        try:
            password_validation.validate_password(attrs["password"], User(email=attrs["email"], username=attrs["email"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        password = validated_data.pop("password")
        category = validated_data.pop("category")
        email = validated_data.pop("email")
        phone = validated_data.pop("contact_phone", "")
        user = User.objects.create_user(username=email, password=password, email=email)
        user.account_profile.phone_number = phone
        user.account_profile.save(update_fields=("phone_number", "updated_at"))
        profile = ProfessionalProfile.objects.create(
            account=user.account_profile,
            category=category,
            contact_email=email,
            contact_phone=phone,
            **validated_data,
        )
        record_event(actor=user, action="professional_registration.created", target=profile, request=request)
        return user, profile


class ProfessionalLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class CsrfCookieSerializer(serializers.Serializer):
    csrf = serializers.CharField()


class AuthSessionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    email = serializers.EmailField()
    account_status = serializers.CharField(source="account_profile.status")
    roles = serializers.SerializerMethodField()
    professional_profile_id = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, user):
        return list(user.groups.values_list("name", flat=True))

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_professional_profile_id(self, user):
        try:
            return user.account_profile.professional_profile.pk
        except ProfessionalProfile.DoesNotExist:
            return None
