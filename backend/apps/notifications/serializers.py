from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_label = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id", "notification_type", "notification_type_label", "title", "body",
            "target_type", "target_id", "link", "whatsapp_link", "read_at", "created_at",
        )
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ("whatsapp_opt_in", "consent_at", "updated_at")
        read_only_fields = ("consent_at", "updated_at")


class MarkReadSerializer(serializers.Serializer):
    pass
