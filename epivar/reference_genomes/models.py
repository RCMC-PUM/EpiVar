import os
import hashlib

from django.db import models
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from pybedtools import BedTool
from liftover import ChainFile as CF


def upload_chain_file(instance, name):
    return os.path.join(
        "reference_data", instance.source_genome.name, "chain_files/", name
    )


def upload_annotation_file(instance, name):
    return os.path.join("reference_data", instance.name, "annotations/", name)


def upload_chrom_size_file(instance, name):
    return os.path.join("reference_data", instance.name, "chrom_size/", name)


def upload_genomic_features_file(instance, name):
    return os.path.join(
        "reference_data", instance.reference_genome.name, "features/", name
    )


def test_annotation_file(file):
    file_type = BedTool(file.path).file_type
    if file_type != "gff":
        raise ValidationError("Parsing error: only gff files are supported!")


def test_index_file(file):
    if not file.name.endswith(".tbi"):
        raise ValidationError("Only .tbi files are allowed.")


def test_chain_file(file):
    try:
        CF(file.path)
    except Exception as e:
        ValidationError(f"Chain file validation error: {e}")


def test_genomic_features_file(file):
    if not file.name.endswith(".bed.gz"):
        raise ValidationError("Only .bed .bedpe .bigwig files are allowed.")


class Assembly(models.TextChoices):
    HG19 = "hg19", "hg19"
    HG38 = "hg38", "hg38"
    T2T = "T2T", "T2T"


# Create storage that allows overwriting files
overwrite_storage = FileSystemStorage(allow_overwrite=True, file_permissions_mode=0o666)


class ReferenceGenome(models.Model):
    name = models.CharField(choices=Assembly.choices, default=Assembly.HG38)
    version = models.CharField(max_length=50, unique=True)

    annotations_file = models.FileField(
        upload_to=upload_annotation_file,
        validators=[test_annotation_file],
        storage=overwrite_storage,
    )
    annotations_file_checksum = models.CharField(blank=True, null=True, editable=True)

    annotations_file_index = models.FileField(
        upload_to=upload_annotation_file,
        validators=[test_index_file],
        storage=overwrite_storage,
        null=True,
        blank=True,
        editable=False,
    )
    annotations_file_index_checksum = models.CharField(
        blank=True, null=True, editable=True
    )

    chrom_size_file = models.FileField(
        upload_to=upload_chrom_size_file, storage=overwrite_storage
    )
    chrom_size_file_checksum = models.CharField(blank=True, null=True, editable=True)

    chrom_size_file_bed = models.FileField(
        upload_to=upload_chrom_size_file,
        storage=overwrite_storage,
        null=True,
        blank=True,
        editable=False,
    )
    chrom_size_file_bed_checksum = models.CharField(
        blank=True, null=True, editable=True
    )

    chrom_size_file_bed_index = models.FileField(
        upload_to=upload_chrom_size_file,
        storage=overwrite_storage,
        null=True,
        blank=True,
        editable=False,
    )
    chrom_size_file_bed_index_checksum = models.CharField(
        blank=True, null=True, editable=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Reference Genomes"

    def __str__(self):
        return f"{self.name} ({self.version})"

    @staticmethod
    def _calculate_checksum(file_field):
        if not file_field:
            return ""

        md5 = hashlib.md5()
        for chunk in file_field.chunks(chunk_size=64):
            md5.update(chunk)
        return md5.hexdigest()

    def save(self, *args, **kwargs):
        # Update checksums
        if self.annotations_file:
            self.annotations_file.open("rb")
            self.annotations_file_checksum = self._calculate_checksum(
                self.annotations_file
            )

        if self.annotations_file_index:
            self.annotations_file_index.open("rb")
            self.annotations_file_index_checksum = self._calculate_checksum(
                self.annotations_file_index
            )

        if self.chrom_size_file:
            self.chrom_size_file.open("rb")
            self.chrom_size_file_checksum = self._calculate_checksum(
                self.chrom_size_file
            )

        if self.chrom_size_file_bed:
            self.chrom_size_file_bed.open("rb")
            self.chrom_size_file_bed_checksum = self._calculate_checksum(
                self.chrom_size_file_bed
            )

        if self.chrom_size_file_bed_index:
            self.chrom_size_file_bed_index.open("rb")
            self.chrom_size_file_bed_index_checksum = self._calculate_checksum(
                self.chrom_size_file_bed_index
            )

        super().save(*args, **kwargs)


class ChainFile(models.Model):
    source_genome = models.ForeignKey(
        ReferenceGenome, related_name="source_genome", on_delete=models.CASCADE
    )
    target_genome = models.ForeignKey(
        ReferenceGenome, related_name="target_genome", on_delete=models.CASCADE
    )
    file = models.FileField(
        upload_to=upload_chain_file,
        storage=overwrite_storage,
        validators=[test_chain_file],
    )
    file_checksum = models.CharField(blank=True, null=True, editable=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Chain Files"

    def __str__(self):
        return f"Chain from {self.source_genome.name} to {self.target_genome.name}"

    @staticmethod
    def _calculate_checksum(file_field):
        if not file_field:
            return ""

        md5 = hashlib.md5()

        for chunk in file_field.chunks(chunk_size=64):
            md5.update(chunk)

        return md5.hexdigest()

    def save(self, *args, **kwargs):
        if self.file:
            self.file.open("rb")
            self.file_checksum = self._calculate_checksum(self.file)

        super().save(*args, **kwargs)


class GenomicFeatureCollection(models.Model):
    """
    A logical grouping of multiple GenomicFeatures
    (e.g., 15-state-core-model for CD4).
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    reference = models.TextField(blank=True, null=True)
    reference_url = models.URLField(blank=True, null=True)
    reference_genome = models.ForeignKey(
        ReferenceGenome, on_delete=models.CASCADE, related_name="feature_collections"
    )

    class Meta:
        verbose_name_plural = "Genomic Feature Collections"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GenomicFeature(models.Model):
    """
    Individual feature (e.g., one state BED file)
    that can belong to a collection.
    """

    collection = models.ForeignKey(
        GenomicFeatureCollection,
        on_delete=models.CASCADE,
        related_name="features",
        null=True,
        blank=True,
    )

    name = models.CharField(null=False, blank=False, unique=True)
    description = models.CharField(null=False, blank=False)

    reference = models.TextField(null=True, blank=True)
    reference_url = models.URLField(null=True, blank=True)
    reference_genome = models.ForeignKey(ReferenceGenome, on_delete=models.CASCADE)

    file = models.FileField(
        upload_to=upload_genomic_features_file,
        validators=[test_genomic_features_file],
        storage=overwrite_storage,
        blank=True,
    )
    file_checksum = models.CharField(blank=True, null=True, editable=False)

    file_index = models.FileField(
        upload_to=upload_genomic_features_file,
        validators=[test_index_file],
        blank=True,
        null=True,
        editable=False,
        storage=overwrite_storage,
    )
    file_index_checksum = models.CharField(blank=True, null=True, editable=False)

    class Meta:
        verbose_name_plural = "Genomic Features"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

    @staticmethod
    def _calculate_checksum(file_field):
        if not file_field:
            return ""
        md5 = hashlib.md5()
        for chunk in file_field.chunks(chunk_size=64):
            md5.update(chunk)
        return md5.hexdigest()

    def save(self, *args, **kwargs):
        if self.file:
            self.file.open("rb")
            self.file_checksum = self._calculate_checksum(self.file)

        if self.file_index:
            self.file_index.open("rb")
            self.file_index_checksum = self._calculate_checksum(self.file_index)

        super().save(*args, **kwargs)


class GeneSetCollection(models.TextChoices):
    HALLMARK = "H", "Hallmark"
    C1 = "C1", "Positional gene sets"
    C2 = "C2", "Curated gene sets"
    C3 = "C3", "Regulatory target gene sets"
    C4 = "C4", "Computational gene sets"
    C5 = "C5", "Ontology gene sets"
    C6 = "C6", "Oncogenic signature gene sets"
    C7 = "C7", "Immunologic signature gene sets"
    C8 = "C8", "Cell type signature gene sets"


class GeneSet(models.Model):
    name = models.CharField(unique=True, max_length=512)

    collection = models.CharField(choices=GeneSetCollection)
    subcollection = models.CharField(blank=False, null=True)
    subset = models.CharField(blank=False, null=True)

    exact_source = models.CharField(blank=True, null=True)
    external_details_url = models.URLField(blank=True, null=True)

    systematic_name = models.CharField(max_length=50)
    pmid = models.CharField(blank=True, null=True)

    reference = models.TextField(blank=True, null=True)
    reference_url = models.URLField(blank=True, null=True)
    genes = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "collection", "subcollection"], name="unique_gene_set"
            ),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.collection}]"
