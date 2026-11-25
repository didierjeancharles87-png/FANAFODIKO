from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProfessionalDocument


@receiver(post_delete, sender=ProfessionalDocument)
def delete_private_document_after_commit(sender, instance, **kwargs):
    if instance.file:
        storage = instance.file.storage
        name = instance.file.name
        transaction.on_commit(lambda: storage.delete(name))
