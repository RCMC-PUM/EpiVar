import os
from django.db import models
from pgvector.django import VectorField
from polymorphic.models import PolymorphicModel
from django.core.exceptions import ValidationError
from django_celery_results.models import TaskResult
from django.core.validators import MinValueValidator
from django.core.files.storage import FileSystemStorage

from ontologies.models import AnatomicalStructure, CellType, Term
from reference_genomes.models import ReferenceGenome
from users.models import User

####################
# Constants
# ####################
ALLOWED_EXTENSIONS = ("bed.gz", "bedpe.gz")


def validate_file_name(file):
    if not file.name.lower().endswith(ALLOWED_EXTENSIONS):
        raise ValidationError(
            f"File must be a bgzipped BED or BEDPE file ({', '.join(ALLOWED_EXTENSIONS)})."
        )


####################
# Files storage
# ####################
overwrite_storage = FileSystemStorage(file_permissions_mode=0o666)


def data_path(instance, filename):
    return os.path.join("studies", "submitted", filename)


####################
# Enums
####################
class RecordStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DEPRECATED = "deprecated", "Deprecated"
    REVIEW = "review", "Under Review"


class IntegrationStatus(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"


class InteractionType(models.TextChoices):
    GENOME_GENOME = "genome-genome", "Genome ↔ Genome (e.g. chromatin loops)"
    EPIGENOME_EPIGENOME = (
        "epigenome-epigenome",
        "Epigenome ↔ Epigenome (e.g. histone marks crosstalk)",
    )
    EPIGENOME_TRANSCRIPTOME = "epigenome-transcriptome", (
        "Epigenome ↔ Transcriptome (e.g. methylation-expression correlation)"
    )


class Replicates(models.TextChoices):
    BIOLOGICAL = "biological", "Biological"
    TECHNICAL = "technical", "Technical"
    UNREPLICATED = "unreplicated", "Unreplicated"


class DataBases(models.TextChoices):
    SRA = "sra", "SRA"
    GEO = "geo", "GEO"
    EGA = "ega", "EGA"
    array_express = "array_express", "Array Express"


####################
# Base model
####################
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


####################
# Project model
####################
class Project(TimestampedModel):
    project_id = models.CharField(unique=True, editable=False)
    title = models.CharField(max_length=255)

    authors = models.TextField()
    contact = models.EmailField(blank=True, null=True)

    affiliation = models.TextField()
    description = models.TextField()

    submitter = models.ForeignKey(User, on_delete=models.PROTECT, null=True)

    class Meta:
        verbose_name_plural = "Projects"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.pk:
            last = Project.objects.order_by("-pk").first()
            next_id = (last.pk + 1) if last else 1
            self.project_id = f"EPIP{next_id:06d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.project_id


class Biosample(models.Model):
    tissue = models.ForeignKey(
        AnatomicalStructure, on_delete=models.PROTECT, related_name="+",
    )
    cell = models.ForeignKey(
        CellType, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    cell_line = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "cell_line"},
        related_name="+",
        null=True,
        blank=True
    )
    analyte = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "analyte"},
        related_name="+",
    )


class Platform(models.Model):
    platform = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "platform"},
        related_name="+",
    )
    assay = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "assay"},
        related_name="+",
    )
    target = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "target"},
        related_name="+",
    )


class Sample(models.Model):
    sample_size = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    replication_type = models.CharField(
        choices=Replicates.choices, default=Replicates.BIOLOGICAL
    )


class Phenotype(models.Model):
    hpo = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "phenotype"},
        related_name="+",
    )


class Investigation(models.Model):
    investigation_model = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "investigation_model"},
        related_name="+",
    )
    statistical_test = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "statistical_test"},
        related_name="+",
    )
    effect_size_metric = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        limit_choices_to={"category": "effect_size_metric"},
        related_name="+",
    )


class DataStorage(models.Model):
    raw_data_storage = models.CharField(
        choices=DataBases.choices, blank=True, null=True
    )
    raw_data_accession_number = models.CharField(max_length=255, blank=True, null=True)


class StudyData(models.Model):
    reference_genome = models.ForeignKey(ReferenceGenome, on_delete=models.PROTECT)

    data = models.FileField(
        upload_to=data_path, validators=[validate_file_name], storage=overwrite_storage
    )
    data_checksum = models.CharField(editable=False, null=True, blank=True)
    metadata = models.JSONField(editable=False, null=True, blank=True)


class Embedding(models.Model):
    text = models.CharField(editable=False)
    embedding = VectorField(dimensions=384, editable=False)


####################
# Study model
####################
class Study(PolymorphicModel, TimestampedModel):
    study_id = models.CharField(unique=True, editable=False)

    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, null=True, blank=True
    )
    submitter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="+"
    )

    record_status = models.CharField(
        choices=RecordStatus.choices, default=RecordStatus.REVIEW
    )
    title = models.CharField(max_length=255)
    reference = models.CharField(blank=True, null=True)

    overall_description = models.TextField(max_length=1000)
    sample_processing_description = models.TextField(max_length=1000)

    data_processing_description = models.TextField(max_length=1000)
    embedding = models.OneToOneField(
        Embedding, on_delete=models.CASCADE, editable=False, null=True, blank=True
    )
    raw_data_storage = models.OneToOneField(DataStorage, on_delete=models.CASCADE, null=True, blank=True)

    integration_task = models.ForeignKey(
        TaskResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    integration_status = models.CharField(
        choices=IntegrationStatus.choices, default=IntegrationStatus.PENDING
    )

    class Meta:
        abstract = True

    def assign_study_id(self, prefix):
        if not self.study_id:
            last = self.__class__.objects.order_by("-pk").first()
            next_id = (last.pk + 1) if last else 1
            self.study_id = f"{prefix}{next_id:06d}"

    # def clean(): add validation here
    # def assign_random_reviewer(self):
    #     # TODO Move to signals
    #     if self.submitter:
    #         reviewers = User.objects.filter(is_reviewer=True).exclude(id=self.submitter.id)
    #         if reviewers.exists():
    #             self.reviewer = random.choice(list(reviewers))

    def save(self, *args, **kwargs):
        # self.assign_random_reviewer()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.project:
            return f"{self.study_id} [{self.project.project_id}]"
        return f"{self.study_id}"


class AssociationStudy(Study):
    biosample = models.OneToOneField(Biosample, on_delete=models.CASCADE, null=True)
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE, null=True)

    platform = models.OneToOneField(Platform, on_delete=models.CASCADE, null=True)
    phenotype = models.OneToOneField(Phenotype, on_delete=models.CASCADE, null=True)

    investigation_model = models.OneToOneField(
        Investigation, on_delete=models.CASCADE, null=True
    )
    submitted_data = models.OneToOneField(
        StudyData, on_delete=models.CASCADE, related_name="sd_association_study"
    )
    preprocessed_data = models.OneToOneField(
        StudyData,
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True,
        related_name="ps_association_study",
    )

    class Meta:
        verbose_name = "Association Study"
        verbose_name_plural = "Association Studies"

    def save(self, *args, **kwargs):
        self.assign_study_id("PAS")
        super().save(*args, **kwargs)

    @property
    def study_type(self):
        return "Association study"


class InteractionStudy(Study):
    interaction_type = models.CharField(
        choices=InteractionType.choices, default=InteractionType.GENOME_GENOME
    )

    biosample = models.OneToOneField(Biosample, on_delete=models.CASCADE, null=True)
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE, null=True)

    platform = models.OneToOneField(Platform, on_delete=models.CASCADE, null=True)
    phenotype = models.OneToOneField(Phenotype, on_delete=models.CASCADE, null=True, blank=True)
    investigation_model = models.OneToOneField(
        Investigation, on_delete=models.CASCADE, null=True
    )

    submitted_data = models.OneToOneField(
        StudyData, on_delete=models.CASCADE, related_name="sd_interaction_study"
    )
    preprocessed_data = models.OneToOneField(
        StudyData,
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True,
        related_name="ps_interaction_study",
    )

    class Meta:
        verbose_name = "Interaction Study"
        verbose_name_plural = "Interaction Studies"

    def save(self, *args, **kwargs):
        self.assign_study_id("MIS")
        super().save(*args, **kwargs)

    @property
    def study_type(self):
        return "Interaction study"


class ProfilingStudy(Study):
    biosample = models.OneToOneField(Biosample, on_delete=models.CASCADE, null=True)
    platform = models.OneToOneField(Platform, on_delete=models.CASCADE, null=True)
    sample = models.OneToOneField(Sample, on_delete=models.CASCADE, null=True)

    phenotype = models.OneToOneField(Phenotype, on_delete=models.CASCADE, null=True, blank=True)
    submitted_data = models.OneToOneField(
        StudyData, on_delete=models.CASCADE, related_name="sd_profiling_study"
    )
    preprocessed_data = models.OneToOneField(
        StudyData,
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True,
        related_name="pd_profiling_study",
    )

    class Meta:
        verbose_name = "Profiling Study"
        verbose_name_plural = "Profiling Studies"

    def save(self, *args, **kwargs):
        self.assign_study_id("MPS")
        super().save(*args, **kwargs)

    @property
    def study_type(self):
        return "Profiling study"
