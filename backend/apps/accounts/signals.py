from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AccountProfile
from .services import invalidate_user_sessions


@receiver(post_save, sender=get_user_model())
def ensure_account_profile(sender, instance, created, **kwargs):
    if created:
        AccountProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=AccountProfile)
def revoke_sessions_on_suspension(sender, instance, raw, update_fields, **kwargs):
    if raw or not instance.pk:
        return
    if update_fields is not None and "status" not in update_fields:
        return
    if instance.status not in (AccountProfile.Status.SUSPENDED, AccountProfile.Status.CLOSED):
        return
    previous = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    if previous != instance.status:
        invalidate_user_sessions(user_id=instance.user_id)


@receiver(pre_save, sender=get_user_model())
def revoke_sessions_on_user_deactivation(sender, instance, raw, update_fields, **kwargs):
    if raw or not instance.pk or instance.is_active:
        return
    if update_fields is not None and "is_active" not in update_fields:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list("is_active", flat=True).first()
    if previous:
        invalidate_user_sessions(user=instance)
