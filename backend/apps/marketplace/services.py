from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.categories import ProfessionalCategory
from apps.accounts.models import AccountProfile
from apps.audit.services import record_event
from apps.notifications.services import notify_moderation_decision, notify_stock_depleted
from apps.professionals.models import ProfessionalProfile

from .models import CatalogProduct, CatalogSeller, ProductImage, ProductPriceHistory, SellerOwner


def assign_seller_owner(*, seller, account, actor, request=None):
    """Attache explicitement un compte actif à un vendeur existant."""
    errors = {}

    if SellerOwner.objects.filter(seller=seller).exists():
        errors["seller"] = "Ce vendeur possède déjà un propriétaire."
    if SellerOwner.objects.filter(account=account).exists():
        errors["account"] = "Ce compte possède déjà un vendeur."
    if account.status != AccountProfile.Status.ACTIVE or not account.user.is_active:
        errors["account"] = "Le compte propriétaire doit être actif."

    if seller.kind == CatalogSeller.Kind.PHARMACY:
        try:
            profile = account.professional_profile
        except ProfessionalProfile.DoesNotExist:
            profile = None
        if not profile:
            errors["account"] = "Le propriétaire d'une pharmacie doit avoir un profil professionnel."
        else:
            if profile.category != ProfessionalCategory.PHARMACY:
                errors["account"] = "Le profil du propriétaire doit être celui d'une pharmacie."
            if profile.verification_status != ProfessionalProfile.VerificationStatus.APPROVED:
                errors["account"] = "Le profil pharmacie du propriétaire doit être approuvé."
            if not account.user.groups.filter(name="professional_verified").exists():
                errors["account"] = "Le profil pharmacie du propriétaire doit être vérifié."
            if seller.professional_profile_id != profile.pk:
                errors["seller"] = "La pharmacie attribuée doit correspondre au profil du propriétaire."
            if profile.account_id != account.pk:
                errors["account"] = "Ce profil professionnel n'appartient pas au compte cible."
    elif seller.kind == CatalogSeller.Kind.MEDICAL_SUPPLIER and not seller.verification_reference.strip():
        errors["seller"] = "Un fournisseur doit conserver sa référence de vérification."

    if errors:
        raise ValidationError(errors)

    with transaction.atomic():
        assignment = SellerOwner(
            account=account,
            seller=seller,
            created_by=actor,
            updated_by=actor,
        )
        assignment.full_clean()
        assignment.save()
        record_event(
            actor=actor,
            action="marketplace.seller_owner.assigned",
            target=assignment,
            request=request,
            metadata={
                "seller_id": seller.pk,
                "account_id": account.pk,
                "account_username": account.user.get_username(),
                "assigned_at": timezone.now().isoformat(),
            },
        )
    return assignment


def record_price_change(product, *, actor, reason=""):
    """Consigne un prix réellement appliqué, sans aucune valeur rétroactive."""
    return ProductPriceHistory.objects.create(
        product=product,
        price_mga=product.price_mga,
        changed_by=actor,
        reason=reason[:200],
    )


def sync_primary_image(product, image, *, actor):
    """Reflète l'image principale de la galerie sur le champ historique CatalogProduct.image."""
    product.image.name = image.file.name if image else ""
    product.updated_by = actor
    product.save(update_fields=("image", "updated_by", "updated_at"))


def set_primary_product_image(image, *, actor, request=None):
    with transaction.atomic():
        ProductImage.objects.filter(product=image.product, is_primary=True).exclude(pk=image.pk).update(
            is_primary=False
        )
        image.is_primary = True
        image.save(update_fields=("is_primary", "updated_at"))
        sync_primary_image(image.product, image, actor=actor)
        record_event(
            actor=actor,
            action="marketplace.image.primary_set",
            target=image,
            request=request,
            metadata={"product_id": image.product_id},
        )
    return image


def delete_product_image(image, *, actor, request=None):
    product = image.product
    image_id = image.pk
    was_primary = image.is_primary
    storage = image.file.storage
    filename = image.file.name
    with transaction.atomic():
        image.delete()
        if was_primary:
            replacement = ProductImage.objects.filter(product=product).order_by("sort_order", "created_at").first()
            if replacement:
                set_primary_product_image(replacement, actor=actor, request=request)
            else:
                sync_primary_image(product, None, actor=actor)
        record_event(
            actor=actor,
            action="marketplace.image.deleted",
            target=product,
            request=request,
            metadata={"product_id": product.pk, "image_id": image_id},
        )
    if filename:
        transaction.on_commit(lambda: storage.delete(filename))


def submit_product_for_review(product, *, actor, request=None):
    if product.status == CatalogProduct.Status.ARCHIVED:
        raise ValidationError({"status": "Un produit archivé ne peut pas être soumis à modération."})
    with transaction.atomic():
        product.status = CatalogProduct.Status.DRAFT
        product.moderation_status = CatalogProduct.ModerationStatus.PENDING
        product.submitted_for_review_at = timezone.now()
        product.reviewed_by = None
        product.reviewed_at = None
        product.review_notes = ""
        product.updated_by = actor
        product.full_clean()
        product.save()
        record_event(
            actor=actor,
            action="marketplace.product.submitted",
            target=product,
            request=request,
            metadata={"submitted_at": product.submitted_for_review_at.isoformat()},
        )
    return product


def approve_product(product, *, actor, request=None):
    if product.moderation_status != CatalogProduct.ModerationStatus.PENDING:
        raise ValidationError({"moderation_status": "Seul un produit en attente peut être approuvé."})
    with transaction.atomic():
        product.status = CatalogProduct.Status.PUBLISHED
        product.moderation_status = CatalogProduct.ModerationStatus.APPROVED
        product.reviewed_by = actor
        product.reviewed_at = timezone.now()
        product.review_notes = ""
        product.updated_by = actor
        try:
            product.full_clean()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        product.save()
        record_event(
            actor=actor,
            action="marketplace.product.approved",
            target=product,
            request=request,
            metadata={"reviewed_at": product.reviewed_at.isoformat()},
        )
        notify_moderation_decision(product, approved=True)
    return product


def reject_product(product, *, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Le motif du rejet est obligatoire."})
    if product.moderation_status != CatalogProduct.ModerationStatus.PENDING:
        raise ValidationError({"moderation_status": "Seul un produit en attente peut être refusé."})
    with transaction.atomic():
        product.status = CatalogProduct.Status.DRAFT
        product.moderation_status = CatalogProduct.ModerationStatus.REJECTED
        product.reviewed_by = actor
        product.reviewed_at = timezone.now()
        product.review_notes = reason
        product.updated_by = actor
        product.full_clean()
        product.save()
        record_event(
            actor=actor,
            action="marketplace.product.rejected",
            target=product,
            request=request,
            metadata={"reviewed_at": product.reviewed_at.isoformat(), "reason": reason},
        )
        notify_moderation_decision(product, approved=False)
    return product


def _authorization_product(product):
    if product.product_type != CatalogProduct.ProductType.MEDICINE:
        raise ValidationError({"product_type": "La vérification AMM s’applique uniquement aux médicaments."})
    if product.status == CatalogProduct.Status.ARCHIVED:
        raise ValidationError({"status": "Une fiche archivée ne peut pas être décidée."})
    return product


def verify_authorization(product, *, actor, request=None):
    """Décision administrative : la référence déclarée devient la référence vérifiée."""
    product = _authorization_product(product)
    reference = (product.authorization_reference or "").strip()
    if not reference:
        raise ValidationError({"authorization_reference": "Une référence AMM est requise pour la vérification."})
    with transaction.atomic():
        previous_status = product.authorization_status
        now = timezone.now()
        product.authorization_status = CatalogProduct.AuthorizationStatus.VERIFIED
        product.authorization_verified_reference = reference
        product.authorization_submitted_at = product.authorization_submitted_at or now
        product.authorization_reviewed_by = actor
        product.authorization_reviewed_at = now
        product.authorization_review_notes = ""
        product.authorization_decision_tracked = True
        product.updated_by = actor
        try:
            product.full_clean()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        product.save()
        record_event(
            actor=actor,
            action="marketplace.authorization.verified",
            target=product,
            request=request,
            metadata={
                "previous_status": previous_status,
                "reference": reference,
                "reviewed_at": now.isoformat(),
            },
        )
    return product


def reject_authorization(product, *, actor, reason, request=None):
    """Décision administrative de refus ; le motif est conservé avec la décision."""
    product = _authorization_product(product)
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValidationError({"reason": "Le motif du refus AMM est obligatoire."})
    with transaction.atomic():
        previous_status = product.authorization_status
        now = timezone.now()
        product.authorization_status = CatalogProduct.AuthorizationStatus.REJECTED
        product.authorization_verified_reference = ""
        product.authorization_reviewed_by = actor
        product.authorization_reviewed_at = now
        product.authorization_review_notes = clean_reason[:500]
        product.authorization_decision_tracked = True
        product.updated_by = actor
        if product.status == CatalogProduct.Status.PUBLISHED:
            product.status = CatalogProduct.Status.DRAFT
        try:
            product.full_clean()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        product.save()
        record_event(
            actor=actor,
            action="marketplace.authorization.rejected",
            target=product,
            request=request,
            metadata={
                "previous_status": previous_status,
                "reason": clean_reason[:500],
                "reviewed_at": now.isoformat(),
            },
        )
    return product


def reopen_authorization(product, *, actor, request=None):
    """Rouvre une décision AMM en attente d'une nouvelle vérification."""
    product = _authorization_product(product)
    with transaction.atomic():
        previous_status = product.authorization_status
        product.authorization_status = CatalogProduct.AuthorizationStatus.PENDING
        product.authorization_verified_reference = ""
        product.authorization_reviewed_by = None
        product.authorization_reviewed_at = None
        product.authorization_review_notes = ""
        product.authorization_decision_tracked = False
        product.updated_by = actor
        if product.status == CatalogProduct.Status.PUBLISHED:
            product.status = CatalogProduct.Status.DRAFT
        try:
            product.full_clean()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        product.save()
        record_event(
            actor=actor,
            action="marketplace.authorization.reopened",
            target=product,
            request=request,
            metadata={"previous_status": previous_status},
        )
    return product


def archive_product(product, *, actor, request=None):
    previous_status = product.status
    with transaction.atomic():
        product.status = CatalogProduct.Status.ARCHIVED
        product.updated_by = actor
        product.save(update_fields=("status", "updated_by", "updated_at"))
        record_event(
            actor=actor,
            action="marketplace.product.archived",
            target=product,
            request=request,
            metadata={"previous_status": previous_status},
        )
    return product
