from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import ProfessionalVerificationRequest
from apps.audit.services import record_event

from .models import ProfessionalProfile


@transaction.atomic
def submit_professional_profile(*, profile, actor, request=None):
    if profile.verification_status not in (ProfessionalProfile.VerificationStatus.DRAFT, ProfessionalProfile.VerificationStatus.REJECTED):
        raise ValidationError("Ce profil ne peut pas être soumis dans son état actuel.")
    missing = profile.missing_information
    if missing:
        raise ValidationError({"missing_information": missing})

    details = profile.category_details
    license_number = (getattr(details, "license_number", "") or getattr(details, "registration_number", "")) if details else ""
    if license_number and ProfessionalVerificationRequest.objects.filter(
        status=ProfessionalVerificationRequest.Status.PENDING,
        category=profile.category,
        country=profile.country,
        license_number=license_number,
    ).exists():
        raise ValidationError({"license_number": ["Une demande en attente utilise déjà ce numéro d’autorisation."]})
    verification = ProfessionalVerificationRequest.objects.create(
        user=actor,
        category=profile.category,
        organization_name=profile.legal_name,
        license_number=license_number,
        country=profile.country,
    )
    profile.verification_request = verification
    profile.verification_status = ProfessionalProfile.VerificationStatus.PENDING
    profile.save(update_fields=("verification_request", "verification_status", "updated_at"))
    pending_role, _ = Group.objects.get_or_create(name="professional_pending")
    actor.groups.add(pending_role)
    record_event(actor=actor, action="professional_profile.submitted", target=profile, request=request)
    return profile


@transaction.atomic
def set_professional_account_status(*, profile, actor, status, reason="", request=None):
    from apps.accounts.models import AccountProfile

    if status == AccountProfile.Status.SUSPENDED:
        if profile.account.user_id == actor.pk:
            raise ValidationError("Vous ne pouvez pas suspendre votre propre compte administrateur.")
        if profile.account.status == AccountProfile.Status.SUSPENDED:
            raise ValidationError("Ce compte est déjà suspendu.")
        action = "professional_account.suspended"
    elif status == AccountProfile.Status.ACTIVE:
        if profile.account.status != AccountProfile.Status.SUSPENDED:
            raise ValidationError("Seul un compte suspendu peut être réactivé.")
        action = "professional_account.reactivated"
    else:
        raise ValidationError("Statut de compte non autorisé pour cette opération.")

    profile.account.status = status
    profile.account.save(update_fields=("status", "updated_at"))
    record_event(actor=actor, action=action, target=profile, request=request, metadata={"reason": reason.strip()})
    return profile
