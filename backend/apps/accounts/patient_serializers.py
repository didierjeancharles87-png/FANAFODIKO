from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit.services import record_event
from apps.reference.models import Country
from .models import AccountProfile, BuyerAddress


User = get_user_model()


class PatientRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8, max_length=128)
    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, trim_whitespace=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.filter(is_active=True), required=False, allow_null=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return value

    def validate_phone_number(self, value):
        if value:
            from django.core.validators import RegexValidator
            from django.core.exceptions import ValidationError

            try:
                RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")(value)
            except ValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
        return value.strip()

    def validate(self, attrs):
        candidate = User(email=attrs["email"], username=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"])
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        password = validated_data.pop("password")
        phone = validated_data.pop("phone_number", "")
        country = validated_data.pop("country", None)
        email = validated_data.pop("email")
        user = User.objects.create_user(username=email, email=email, password=password, **validated_data)
        profile = user.account_profile
        profile.phone_number = phone
        profile.country = country
        profile.save(update_fields=("phone_number", "country", "updated_at"))
        from django.contrib.auth.models import Group

        patient_role, _ = Group.objects.get_or_create(name="patient")
        user.groups.add(patient_role)
        record_event(actor=user, action="patient_registration.created", target=profile, request=request)
        return user


class PatientProfileSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, required=False, trim_whitespace=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.filter(is_active=True), required=False, allow_null=True)

    def validate_email(self, value):
        value = value.strip().lower()
        query = User.objects.filter(email__iexact=value) | User.objects.filter(username__iexact=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return value

    def validate_phone_number(self, value):
        if value:
            from django.core.validators import RegexValidator
            from django.core.exceptions import ValidationError

            try:
                RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")(value)
            except ValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
        return value.strip()

    def to_representation(self, user):
        profile = user.account_profile
        return {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": profile.phone_number,
            "country": profile.country_id,
        }

    @transaction.atomic
    def update(self, user, validated_data):
        request = self.context["request"]
        account = user.account_profile
        changed_user = []
        for field in ("first_name", "last_name", "email"):
            if field in validated_data:
                setattr(user, field, validated_data[field])
                changed_user.append(field)
        if "email" in validated_data:
            user.username = validated_data["email"]
            changed_user.append("username")
        if changed_user:
            user.save(update_fields=tuple(dict.fromkeys(changed_user)))
        changed_profile = []
        for field in ("phone_number", "country"):
            if field in validated_data:
                setattr(account, field, validated_data[field])
                changed_profile.append(field)
        if changed_profile:
            account.save(update_fields=(*changed_profile, "updated_at"))
        record_event(actor=user, action="patient_profile.updated", target=account, request=request)
        return user


class BuyerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuyerAddress
        fields = (
            "id", "label", "recipient_name", "phone_number", "country", "region", "city",
            "neighbourhood", "complement", "is_primary", "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_phone_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le téléphone du destinataire est obligatoire.")
        from django.core.validators import RegexValidator
        from django.core.exceptions import ValidationError

        try:
            RegexValidator(r"^\+?[0-9 ()-]{6,20}$", "Saisissez un numéro de téléphone valide.")(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    def validate_country(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Ce pays n’est pas actif.")
        return value

    def validate(self, attrs):
        if not (attrs.get("recipient_name") or "").strip() and not self.instance:
            raise serializers.ValidationError({"recipient_name": "Le nom du destinataire est obligatoire."})
        if not (attrs.get("city") or "").strip() and not self.instance:
            raise serializers.ValidationError({"city": "La ville ou commune est obligatoire."})
        return attrs

    def _ensure_single_primary(self, account, is_primary, instance=None):
        if not is_primary:
            return
        query = BuyerAddress.objects.filter(account=account, is_primary=True, is_active=True)
        if instance:
            query = query.exclude(pk=instance.pk)
        query.update(is_primary=False, updated_at=timezone.now())

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        account = request.user.account_profile
        validated_data["account"] = account
        if not BuyerAddress.objects.filter(account=account, is_active=True).exists():
            validated_data["is_primary"] = True
        self._ensure_single_primary(account, validated_data.get("is_primary"))
        return BuyerAddress.objects.create(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        self._ensure_single_primary(instance.account, validated_data.get("is_primary"), instance=instance)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if not instance.is_active:
            instance.is_primary = False
        instance.save()
        return instance


def is_patient(user):
    return user.groups.filter(name="patient").exists()
