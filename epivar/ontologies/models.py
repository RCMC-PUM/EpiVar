from django.db import models


class OntologyStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DEPRECATED = "deprecated", "Deprecated"


class Ontology(models.Model):
    obo_id = models.CharField(
        max_length=25, unique=True, help_text="OBO resource identifier"
    )
    label = models.CharField(help_text="Human readable name", null=True, blank=True)

    synonyms = models.CharField(help_text="Synonym(s)", null=True, blank=True)
    description = models.TextField(
        help_text="Precise term description", null=True, blank=True
    )

    ontology_name = models.TextField(help_text="Data source", null=True, blank=True)
    iri = models.URLField(help_text="Link to the resource", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Ontology terms"
        ordering = ["-created_at"]
        abstract = True

    def __str__(self):
        return f"{self.label} ({self.obo_id})"


class AnatomicalStructure(Ontology):
    class Meta:
        verbose_name_plural = "Anatomical structures"


class CellType(Ontology):
    anatomical_structure = models.ManyToManyField(
        AnatomicalStructure,
        related_name="cell_types",
        help_text="Anatomical structure this cell type belongs to",
    )

    class Meta:
        verbose_name_plural = "Cell types"


class TermCategory(models.TextChoices):
    INVESTIGATION_MODEL = "investigation_model", "Investigation Model"
    EFFECT_SIZE_METRIC = "effect_size_metric", "Effect size metric"
    STATISTICAL_TEST = "statistical_test", "Statistical test"
    CELL_LINE = "cell_line", "Cell line"
    SUBSTANCE = "substance", "Substance"
    PHENOTYPE = "phenotype", "Phenotype"
    PLATFORM = "platform", "Platform"
    ANALYTE = "analyte", "Analyte"
    TARGET = "target", "Target"
    ASSAY = "assay", "Assay"


class Term(Ontology):
    category = models.CharField(choices=TermCategory.choices)

    class Meta:
        verbose_name_plural = "Experiment Terms"
