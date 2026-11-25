from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import Group
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.middleware.csrf import CSRF_SESSION_KEY
from django.utils import timezone

from apps.audit.services import record_event
from apps.professionals.models import ProfessionalProfile

from .models import ProfessionalVerificationRequest

LOGOUT_ONLY_SESSION_KEY = "logout_only_user_id"


def invalidate_user_sessions(*, user=None, user_id=None):
    """Remplace les sessions authentifiées d'un utilisateur par une session de déconnexion.

    La session conservée ne contient aucune donnée d'authentification Django : elle
    permet uniquement au endpoint de logout de nettoyer le cookie du navigateur.
    """
    if user_id is None and user is not None:
        user_id = getattr(user, "pk", user)
    if user_id is None:
        return 0

    rewritten = 0
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now).iterator():
        try:
            data = session.get_decoded()
        except Exception:
            # Une session illisible n'est pas utilisable ; on la laisse expirer.
            continue
        if str(data.get(SESSION_KEY)) != str(user_id):
            continue

        payload = {LOGOUT_ONLY_SESSION_KEY: user_id}
        if data.get(CSRF_SESSION_KEY):
            payload[CSRF_SESSION_KEY] = data[CSRF_SESSION_KEY]
        session.session_data = SessionStore().encode(payload)
        session.save(update_fields=("session_data",))
        rewritten += 1
    return rewritten


@transaction.atomic
def review_professional_request(*, verification, actor, status, notes="", request=None):
    verification = ProfessionalVerificationRequest.objects.select_for_update().get(pk=verification.pk)
    if verification.status != ProfessionalVerificationRequest.Status.PENDING:
        raise ValidationError("Cette demande a déjà été examinée.")
    if verification.user_id == actor.pk:
        raise ValidationError("Un administrateur ne peut pas examiner sa propre demande.")
    if status not in (ProfessionalVerificationRequest.Status.APPROVED, ProfessionalVerificationRequest.Status.REJECTED):
        raise ValidationError("Le statut de décision est invalide.")

    verification.status = status
    verification.reviewed_by = actor
    verification.reviewed_at = timezone.now()
    verification.review_notes = notes.strip()
    verification.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"))
    professional_profile = ProfessionalProfile.objects.select_for_update().filter(verification_request=verification).first()
    if professional_profile:
        professional_profile.verification_status = (
            ProfessionalProfile.VerificationStatus.APPROVED
            if status == ProfessionalVerificationRequest.Status.APPROVED
            else ProfessionalProfile.VerificationStatus.REJECTED
        )
        professional_profile.save(update_fields=("verification_status", "updated_at"))
        record_event(actor=actor, action=f"professional_profile.{status}", target=professional_profile, request=request)
    pending_role, _ = Group.objects.get_or_create(name="professional_pending")
    verification.user.groups.remove(pending_role)
    if status == ProfessionalVerificationRequest.Status.APPROVED:
        verified_role, _ = Group.objects.get_or_create(name="professional_verified")
        verification.user.groups.add(verified_role)
    record_event(
        actor=actor,
        action=f"professional_verification.{status}",
        target=verification,
        request=request,
    )
    return verification
