from django.db import models

from apps.reference.models import TimestampedModel


class NotificationType(models.TextChoices):
    ORDER_CREATED = "order_created", "Commande créée"
    ORDER_ACCEPTED = "order_accepted", "Commande acceptée"
    ORDER_REJECTED = "order_rejected", "Commande refusée"
    ORDER_PREPARING = "order_preparing", "Commande en préparation"
    ORDER_READY = "order_ready", "Réservation prête"
    ORDER_COMPLETED = "order_completed", "Commande finalisée"
    ORDER_CANCELLED = "order_cancelled", "Commande annulée"
    MODERATION_APPROVED = "moderation_approved", "Produit approuvé"
    MODERATION_REJECTED = "moderation_rejected", "Produit refusé"
    STOCK_DEPLETED = "stock_depleted", "Stock épuisé"


class Notification(TimestampedModel):
    recipient = models.ForeignKey("accounts.AccountProfile", on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=1000)
    target_type = models.CharField(max_length=120, blank=True, db_index=True)
    target_id = models.CharField(max_length=64, blank=True)
    link = models.CharField(max_length=500, blank=True)
    whatsapp_link = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("recipient", "read_at", "created_at"), name="notifications_inbox_idx"),
            models.Index(fields=("target_type", "target_id"), name="notifications_target_idx"),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} — {self.recipient_id}"


class NotificationPreference(TimestampedModel):
    account = models.OneToOneField("accounts.AccountProfile", on_delete=models.CASCADE, related_name="notification_preference")
    whatsapp_opt_in = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Préférences de {self.account_id}"
