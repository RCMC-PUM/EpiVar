import os
import shutil
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_delete

from .models import ReferenceGenome, ChainFile, GenomicFeature


@receiver(post_delete, sender=GenomicFeature)
def remove_genomic_features_related_files(sender, instance, **kwargs):
    if instance.file:
        os.remove(instance.file.path)

    if instance.file_index:
        os.remove(instance.file_index.path)


@receiver(post_delete, sender=GenomicFeature)
def delete_genomic_feature_file(sender, instance, **kwargs):
    if instance.file and os.path.exists(instance.file.path):
        os.remove(instance.file.path)


@receiver(post_delete, sender=ReferenceGenome)
def delete_genome_files(sender, instance, **kwargs):
    ref_genome_name = instance.name
    ref_genome_directory = os.path.join(
        settings.MEDIA_ROOT, "reference_data", ref_genome_name
    )

    if os.path.isdir(ref_genome_directory):
        shutil.rmtree(ref_genome_directory)


@receiver(post_delete, sender=ChainFile)
def delete_chain_file(sender, instance, **kwargs):
    if instance.file and os.path.isfile(instance.file.path):
        os.remove(instance.file.path)
