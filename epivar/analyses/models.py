import os
from django.db import models
from django.core.exceptions import ValidationError
from django_celery_results.models import TaskResult
from django.core.validators import MinValueValidator, MaxValueValidator

from reference_genomes.models import (
    ReferenceGenome,
    GeneSetCollection,
    GenomicFeatureCollection,
)
from users.models import User


def data_path(instance, filename):
    return os.path.join("analyses", filename)


def validate_file(file):
    if not file.path.endswith((".bed", ".bed.gz", ".genes")):
        raise ValidationError(
            "Only files with .bed, .bed.gz (for genomic intervals) or .genes (for GSEA based on genes list) extension "
            "are supported!"
        )


class CorrectionMethod(models.TextChoices):
    BONFERRONI = "bonferroni", "Bonferroni"
    SIDAK = "sidak", "Sidak"
    HOLM = "holm", "Holm"
    HOLMSIDAK = "holm-sidak", "Holm-Sidak"
    SMM = "smm", "Simes-Hochberg"
    HOMMEL = "hommel", "Hommel"
    FDR_BH = "fdr_bh", "Benjamini/Hochberg (FDR)"
    FDR_BY = "fdr_by", "Benjamini/Yekutieli (FDR)"
    FDR_TS_BH = "fdr_tsbh", "Two-stage Benjamini/Hochberg (FDR)"
    FDR_TS_BY = "fdr_tsbky", "Two-stage Benjamini/Krieger/Yekutieli (FDR)"


class BaseAnalysis(models.Model):
    """Abstract base model for all analysis types."""

    submitter = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(default="", max_length=255)

    reference_genome = models.ForeignKey(
        ReferenceGenome, on_delete=models.PROTECT, null=True
    )
    foreground = models.FileField(upload_to=data_path, validators=[validate_file])
    background = models.FileField(
        upload_to=data_path, validators=[validate_file], null=True, blank=True
    )

    require_same_strandedness = models.BooleanField(default=False)
    minimum_overlap_required = models.FloatField(
        default=1e-9,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    significance_level = models.FloatField(
        default=0.05,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    correction_method = models.CharField(
        choices=CorrectionMethod,
        default=CorrectionMethod.FDR_BY,
    )

    results = models.JSONField(null=True, blank=True, editable=False)
    task = models.ForeignKey(
        TaskResult, on_delete=models.SET_NULL, null=True, blank=True, editable=False
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class GSEA(BaseAnalysis):
    """GSEA-specific analysis model."""

    INPUT_TYPE_CHOICES = [
        ("genomic_intervals", "Genomic Intervals"),
        ("gene_names", "Gene Names"),
    ]

    input_type = models.CharField(
        max_length=20, choices=INPUT_TYPE_CHOICES, default="gene_names"
    )
    universe = models.CharField(
        choices=GeneSetCollection, default=None, null=True, blank=True
    )

    n_closest = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    max_absolute_distance = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )

    annotated_foreground = models.FileField(
        upload_to=data_path, editable=False, null=True, blank=True
    )
    annotated_background = models.FileField(
        upload_to=data_path, editable=False, null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "GSEA"

    def __str__(self):
        return "GSEA"


class LOA(BaseAnalysis):
    """LOA-specific analysis model."""
    ALTERNATIVE_CHOICES = (
        ("greater", "Enrichment"),
        ("less", "Depletion"),
        ("two-sided", "Both"),
    )

    universe = models.ManyToManyField(
        GenomicFeatureCollection, blank=False, related_name="loa_universes"
    )
    permutations = models.IntegerField(null=True, blank=True, default=10)
    alternative = models.CharField(
        choices=ALTERNATIVE_CHOICES, max_length=20, default="two-sided"
    )
    lift_over_metrics = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "LOA"

    def __str__(self):
        return "LOA"


class SOA(BaseAnalysis):
    """SOA-specific analysis model."""
    class StudyType(models.TextChoices):
        ASSOCIATION = "association_study", "Association Studies"
        INTERACTION = "interaction_study", "Interaction Studies"
        PROFILING = "profiling_study", "Profiling Studies"

    study_type = models.CharField(
        max_length=50,
        choices=StudyType.choices,
        default=StudyType.ASSOCIATION
    )

    class Meta:
        verbose_name_plural = "SOA"

    def __str__(self):
        return "Study Overlap Analysis"
