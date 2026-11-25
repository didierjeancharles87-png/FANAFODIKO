from .models import AuditEvent


def record_event(*, actor, action, target, request=None, metadata=None):
    remote_addr = None
    if request is not None:
        remote_addr = request.META.get("REMOTE_ADDR")
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        remote_addr=remote_addr,
        metadata=metadata or {},
    )
