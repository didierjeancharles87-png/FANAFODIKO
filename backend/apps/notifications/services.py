import re
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AccountProfile
from apps.audit.services import record_event
from apps.sitecontent.models import SiteConfiguration

from .models import Notification, NotificationPreference, NotificationType

PHONE_PATTERN = re.compile(r"^[1-9]\d{7,14}$")


def get_or_create_preference(account):
    preference, _ = NotificationPreference.objects.get_or_create(account=account)
    return preference


def set_whatsapp_consent(account, *, enabled, actor=None, request=None):
    """Enregistre un consentement explicite et révocable pour les liens WhatsApp."""
    with transaction.atomic():
        preference = get_or_create_preference(account)
        previous = preference.whatsapp_opt_in
        preference.whatsapp_opt_in = bool(enabled)
        preference.consent_at = timezone.now() if enabled else None
        preference.save(update_fields=("whatsapp_opt_in", "consent_at", "updated_at"))
        if previous and not preference.whatsapp_opt_in:
            Notification.objects.filter(recipient=account).exclude(whatsapp_link="").update(whatsapp_link="")
        if previous != preference.whatsapp_opt_in:
            record_event(
                actor=actor,
                action="notifications.whatsapp_consent.changed",
                target=preference,
                request=request,
                metadata={
                    "account_id": account.pk,
                    "enabled": preference.whatsapp_opt_in,
                    "consent_at": preference.consent_at.isoformat() if preference.consent_at else None,
                },
            )
    return preference


def normalized_whatsapp_number():
    """Lit l'unique configuration officielle et valide le numéro, sans valeur de repli."""
    configuration = SiteConfiguration.objects.filter(pk=1).first()
    if not configuration:
        return ""
    compact = re.sub(r"[\s().-]", "", (configuration.whatsapp_number or "").strip()).removeprefix("+")
    if not PHONE_PATTERN.fullmatch(compact):
        return ""
    return compact


def build_whatsapp_link(account, message, *, notification=None):
    """Construit un lien wa.me uniquement après consentement et configuration valide.

    Aucun message n'est envoyé : le lien est seulement proposé à l'utilisateur.
    """
    preference = NotificationPreference.objects.filter(
        account=account, whatsapp_opt_in=True, consent_at__isnull=False
    ).first()
    if not preference:
        return ""
    number = normalized_whatsapp_number()
    if not number:
        return ""

    clean_message = " ".join((message or "").split())[:900]
    if not clean_message:
        return ""
    link = f"https://wa.me/{number}?text={quote(clean_message, safe='')}"

    if notification is not None:
        record_event(
            actor=None,
            action="notifications.whatsapp_link.generated",
            target=notification,
            metadata={
                "account_id": account.pk,
                "notification_type": notification.notification_type,
                "target_type": notification.target_type,
                "target_id": notification.target_id,
                "automatic_delivery": False,
            },
        )
    return link


def create_notification(
    *,
    recipient,
    notification_type,
    title,
    body,
    whatsapp_message="",
    target_type="",
    target_id="",
    link="",
):
    """Crée une notification correspondant à un événement métier réel."""
    if not recipient:
        return None
    if notification_type not in {choice[0] for choice in NotificationType.choices}:
        raise ValueError(f"Type de notification inconnu : {notification_type}")

    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title[:200],
        body=body[:1000],
        target_type=target_type[:120],
        target_id=str(target_id)[:64],
        link=link[:500],
    )
    if whatsapp_message:
        notification.whatsapp_link = build_whatsapp_link(
            recipient, whatsapp_message, notification=notification
        )[:500]
        notification.save(update_fields=("whatsapp_link", "updated_at"))
    return notification


ORDER_STATUS_NOTIFICATIONS = {
    "accepted": NotificationType.ORDER_ACCEPTED,
    "rejected": NotificationType.ORDER_REJECTED,
    "preparing": NotificationType.ORDER_PREPARING,
    "ready": NotificationType.ORDER_READY,
    "completed": NotificationType.ORDER_COMPLETED,
    "cancelled": NotificationType.ORDER_CANCELLED,
}

ORDER_STATUS_TITLES = {
    "accepted": "Commande acceptée",
    "rejected": "Commande refusée",
    "preparing": "Commande en préparation",
    "ready": "Réservation prête pour retrait",
    "completed": "Commande finalisée",
    "cancelled": "Commande annulée",
}

ORDER_STATUS_BODIES = {
    "accepted": "Le partenaire a accepté votre réservation {reference}. Le règlement et le retrait se font auprès du partenaire.",
    "rejected": "Le partenaire a refusé votre réservation {reference}.",
    "preparing": "Votre réservation {reference} est en préparation chez le partenaire.",
    "ready": "Votre réservation {reference} est prête pour retrait auprès du partenaire.",
    "completed": "Votre réservation {reference} est finalisée. Aucun paiement en ligne n'a été effectué.",
    "cancelled": "Votre réservation {reference} a été annulée.",
}


def notify_order_created(order, *, recipient, partner=False):
    link = f"/partenaire/commandes/{order.pk}" if partner else f"/patient/commandes/{order.pk}"
    return create_notification(
        recipient=recipient,
        notification_type=NotificationType.ORDER_CREATED,
        title="Nouvelle réservation" if partner else "Réservation créée",
        body=(
            f"La réservation {order.reference} a été créée pour votre vendeur."
            if partner
            else f"Votre réservation {order.reference} a été enregistrée. Aucun paiement en ligne n'est effectué."
        ),
        whatsapp_message=f"FANAFODIKO — Réservation {order.reference} créée.",
        target_type="orders.order",
        target_id=str(order.pk),
        link=link,
    )


def notify_order_status(order, status, *, recipient, partner=False):
    notification_type = ORDER_STATUS_NOTIFICATIONS.get(status)
    if not notification_type:
        return None
    reference = order.reference
    base_body = ORDER_STATUS_BODIES[status].format(reference=reference)
    if partner and status == "cancelled":
        base_body = f"La réservation {reference} a été annulée par le client."
    link = f"/partenaire/commandes/{order.pk}" if partner else f"/patient/commandes/{order.pk}"
    return create_notification(
        recipient=recipient,
        notification_type=notification_type,
        title=ORDER_STATUS_TITLES[status],
        body=base_body,
        whatsapp_message=f"FANAFODIKO — Réservation {reference} : {ORDER_STATUS_TITLES[status].lower()}.",
        target_type="orders.order",
        target_id=str(order.pk),
        link=link,
    )


def notify_moderation_decision(product, *, approved, actor=None):
    submitter = product.created_by
    if not submitter:
        return None
    account = AccountProfile.objects.filter(user=submitter).first()
    if not account:
        return None
    notification_type = (
        NotificationType.MODERATION_APPROVED if approved else NotificationType.MODERATION_REJECTED
    )
    title = "Produit approuvé" if approved else "Produit refusé"
    body = (
        f"Votre produit « {product.title} » a été approuvé et publié."
        if approved
        else f"Votre produit « {product.title} » a été refusé. Motif : {product.review_notes}."
    )
    return create_notification(
        recipient=account,
        notification_type=notification_type,
        title=title,
        body=body,
        whatsapp_message=f"FANAFODIKO — Produit #{product.pk} : {'approuvé' if approved else 'refusé'}.",
        target_type="marketplace.catalogproduct",
        target_id=str(product.pk),
        link=f"/partenaire/produits/{product.pk}",
    )


def notify_stock_depleted(product, *, actor=None):
    from apps.marketplace.models import SellerOwner

    owners = SellerOwner.objects.filter(seller=product.seller).select_related("account")
    notifications = []
    for owner in owners:
        notifications.append(
            create_notification(
                recipient=owner.account,
                notification_type=NotificationType.STOCK_DEPLETED,
                title="Stock épuisé",
                body=f"Le stock du produit « {product.title} » est épuisé.",
                whatsapp_message=f"FANAFODIKO — Produit #{product.pk} : stock épuisé.",
                target_type="marketplace.catalogproduct",
                target_id=str(product.pk),
                link=f"/partenaire/produits/{product.pk}",
            )
        )
    return notifications
