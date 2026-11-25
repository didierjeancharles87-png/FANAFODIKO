import re
from pathlib import Path

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import FAQEntry, NewsArticle, PageContent, SiteConfiguration, SiteImage


class SiteConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfiguration
        fields = ("whatsapp_number", "updated_at")
        read_only_fields = ("updated_at",)

    def validate_whatsapp_number(self, value):
        compact = re.sub(r"[\s().-]", "", value.strip())
        if compact and not re.fullmatch(r"\+?[1-9]\d{7,14}", compact):
            raise serializers.ValidationError("Saisissez un numéro international valide (8 à 15 chiffres), sans lien WhatsApp.")
        return compact


class FAQEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQEntry
        fields = ("id", "question", "answer", "sort_order", "is_visible", "updated_at")
        read_only_fields = ("id", "updated_at")

    def validate_question(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("La question est obligatoire.")
        return value

    def validate_answer(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("La réponse est obligatoire.")
        return value


class NewsArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        fields = ("id", "title", "slug", "summary", "body", "is_published", "published_at", "updated_at")
        read_only_fields = ("id", "published_at", "updated_at")
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}

    def validate_title(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Le titre est obligatoire.")
        return value

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return NewsArticle.objects.create(**validated_data)


class PageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageContent
        fields = ("id", "page", "title", "introduction", "body", "updated_at")
        read_only_fields = ("id", "updated_at")

    def create(self, validated_data):
        return PageContent.objects.create(updated_by=self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        instance.updated_by = self.context["request"].user
        return super().update(instance, validated_data)


class SiteImageSerializer(serializers.ModelSerializer):
    slot = serializers.ChoiceField(choices=SiteImage.Slot.choices)
    image = serializers.FileField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = SiteImage
        fields = ("id", "slot", "image", "url", "alt_text", "is_visible", "updated_at")
        read_only_fields = ("id", "url", "is_visible", "updated_at")

    def validate_image(self, image):
        if image.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("L’image ne peut pas dépasser 8 Mo.")
        header = image.read(12)
        image.seek(0)
        extension = Path(image.name).suffix.lower()
        signatures = {
            ".jpg": header.startswith(b"\xff\xd8\xff"),
            ".jpeg": header.startswith(b"\xff\xd8\xff"),
            ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
            ".webp": header[:4] == b"RIFF" and header[8:12] == b"WEBP",
        }
        valid = signatures.get(extension, False)
        if not valid:
            raise serializers.ValidationError("Le fichier doit être une image JPEG, PNG ou WebP valide.")
        return image

    @extend_schema_field(serializers.CharField())
    def get_url(self, instance):
        if not instance.is_visible:
            return ""
        request = self.context.get("request")
        version = int(instance.updated_at.timestamp()) if instance.updated_at else 0
        path = f"/api/v1/site-content/public/images/{instance.slot}/?v={version}"
        return request.build_absolute_uri(path) if request else path

    def create(self, validated_data):
        request = self.context["request"]
        existing = SiteImage.objects.filter(slot=validated_data["slot"]).first()
        if existing:
            old = existing.image
            for key, value in validated_data.items():
                setattr(existing, key, value)
            existing.is_visible = True
            existing.updated_by = request.user
            existing.save()
            if old and old.name != existing.image.name:
                old.delete(save=False)
            return existing
        return SiteImage.objects.create(updated_by=request.user, **validated_data)

    def update(self, instance, validated_data):
        old = instance.image
        instance.updated_by = self.context["request"].user
        instance = super().update(instance, validated_data)
        if old and "image" in validated_data and old.name != instance.image.name:
            old.delete(save=False)
        return instance


class SiteConfigurationResponseSerializer(serializers.Serializer):
    whatsapp_number = serializers.CharField()
    updated_at = serializers.DateTimeField(allow_null=True)
    use_database_config = serializers.BooleanField(required=False)


class PublicFAQResponseSerializer(serializers.Serializer):
    managed = serializers.BooleanField()
    entries = FAQEntrySerializer(many=True)


class PublicSiteImageListResponseSerializer(serializers.Serializer):
    images = SiteImageSerializer(many=True)
    hidden_slots = serializers.ListField(child=serializers.CharField())
