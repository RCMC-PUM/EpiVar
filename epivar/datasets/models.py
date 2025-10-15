import os

from django.db import models
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from studies.models import AssociationStudy, InteractionStudy, ProfilingStudy
from reference_genomes.models import ReferenceGenome
from polymorphic.models import PolymorphicModel

from .tasks import update_file_checksum_task

####################
# Constants
####################
FOREGROUND_ALLOWED_EXTENSIONS = ("bed.gz", "bedpe.gz")


def validate_data_name(file):
    if not file.name.lower().endswith(FOREGROUND_ALLOWED_EXTENSIONS):
        raise ValidationError(
            f"Data must be a gzipped BED or BEDPE file ({', '.join(FOREGROUND_ALLOWED_EXTENSIONS)})."
        )


def validate_index_name(file):
    if not file.name.lower().endswith(".tbi"):
        raise ValidationError("Index should have .tbi suffix")


####################
# Files storage
####################
overwrite_storage = FileSystemStorage(allow_overwrite=True, file_permissions_mode=0o666)


def data_path(instance, filename):
    study_id = instance.study.study_id
    reference_genome = instance.reference_genome.name

    return os.path.join("studies", study_id, "prepared", reference_genome, filename)


####################
# Enums
####################
class DataTypes(models.TextChoices):
    bed = "bed", "BED"
    bedpe = "bedpe", "BEDPE"


####################
# Base data model
####################
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseData(TimestampedModel, PolymorphicModel):
    reference_genome = models.ForeignKey(
        ReferenceGenome, on_delete=models.PROTECT, null=False, blank=False
    )
    data = models.FileField(
        upload_to=data_path, validators=[validate_data_name], storage=overwrite_storage
    )

    data_type = models.CharField(choices=DataTypes)
    data_checksum = models.CharField(editable=False, null=True, blank=True)
    data_conversion_metrics = models.JSONField(editable=False, null=True, blank=True)

    data_index = models.FileField(
        upload_to=data_path,
        validators=[validate_index_name],
        storage=overwrite_storage,
        null=True,
        blank=True,
        editable=False,
    )
    data_index_checksum = models.CharField(editable=False, null=True, blank=True)

    annotations = models.FileField(
        upload_to=data_path, storage=overwrite_storage, blank=True, null=True
    )
    annotations_checksum = models.CharField(editable=False, null=True, blank=True)
    annotations_metrics = models.JSONField(blank=True, null=True)

    liftover = models.BooleanField(default=False, editable=False)
    plots = models.JSONField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.data:
            if self.data.path:
                update_file_checksum_task.delay_on_commit(
                    "datasets",
                    self.__class__.__name__,
                    self.id,
                    "data",
                    "data_checksum",
                )

        if self.data_index:
            if self.data_index.path:
                update_file_checksum_task.delay_on_commit(
                    "datasets",
                    self.__class__.__name__,
                    self.id,
                    "data_index",
                    "data_index_checksum",
                )

        if self.annotations:
            if self.annotations.path:
                update_file_checksum_task.delay_on_commit(
                    "datasets",
                    self.__class__.__name__,
                    self.id,
                    "annotations",
                    "annotations_checksum",
                )

        super().save(*args, **kwargs)


####################
# Data subclasses
####################
class AssociationData(BaseData):
    study = models.ForeignKey(
        AssociationStudy,
        on_delete=models.CASCADE,
        related_name="phenotypic_association_data",
    )

    class Meta:
        verbose_name_plural = "Association Data"

    def __str__(self):
        return f"Association Data [{self.study.study_id}]"


class InteractionData(BaseData):
    study = models.ForeignKey(
        InteractionStudy, on_delete=models.CASCADE, related_name="interaction_data"
    )

    class Meta:
        verbose_name_plural = "Interaction Data"

    def __str__(self):
        return f"Interaction Data [{self.study.study_id}]"


class ProfilingData(BaseData):
    study = models.ForeignKey(
        ProfilingStudy, on_delete=models.CASCADE, related_name="profiling_data"
    )

    class Meta:
        verbose_name_plural = "Profiling Data"

    def __str__(self):
        return f"Profiling Data [{self.study.study_id}]"
