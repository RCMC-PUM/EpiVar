import os
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.core.files.storage import default_storage

from .models import GSEA, LOA, SOA


def delete_file_if_exists(file_path):
    """Helper to remove a file if it exists in storage."""
    if file_path:
        if os.path.exists(file_path):
            os.remove(file_path)


@receiver(post_delete, sender=GSEA)
@receiver(post_delete, sender=LOA)
@receiver(post_delete, sender=SOA)
def delete_associated_files(sender, instance, **kwargs):
    """
    Delete file fields after model deletion.
    Works for all models inheriting from BaseAnalysis.
    """
    # Always remove foreground & background
    delete_file_if_exists(instance.foreground.path)
    delete_file_if_exists(instance.foreground.path)

    # Model-specific cleanup
    if isinstance(instance, GSEA):
        delete_file_if_exists(instance.annotated_foreground.path)
        delete_file_if_exists(instance.annotated_background.path)
