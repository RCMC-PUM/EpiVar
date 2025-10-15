from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import ChainFile, ReferenceGenome, GenomicFeature, GenomicFeatureCollection, GeneSet


class GenomicFeatureInline(admin.TabularInline):
    model = GenomicFeature
    extra = 0
    fields = ("name", "description")
    readonly_fields = ("name", "description")
    show_change_link = True


@admin.register(GenomicFeatureCollection)
class GenomicFeatureCollectionAdmin(VersionAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")
    inlines = [GenomicFeatureInline]


@admin.register(GenomicFeature)
class GenomicFeatureAdmin(VersionAdmin):
    list_display = ("name", "description", "collection__name")
    search_fields = ("name", "description", "collection__name")
    readonly_fields = ("file_checksum", "file_index_checksum")


@admin.register(ChainFile)
class ChainFileAdmin(VersionAdmin):
    readonly_fields = ("file_checksum",)


@admin.register(ReferenceGenome)
class ReferenceGenomeAdmin(VersionAdmin):
    readonly_fields = (
        "chrom_size_file_bed",
        "chrom_size_file_bed_index",
        "annotations_file_checksum",
        "annotations_file_index",
        "annotations_file_index_checksum",
        "chrom_size_file_checksum",
        "chrom_size_file_bed_checksum",
        "chrom_size_file_bed_index_checksum",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("General Information", {"fields": ("name", "version")}),
        (
            "Annotation Files",
            {
                "fields": (
                    "annotations_file",
                    "annotations_file_checksum",
                    "annotations_file_index",
                    "annotations_file_index_checksum",
                )
            },
        ),
        (
            "Chromosome Sizes",
            {
                "fields": (
                    "chrom_size_file",
                    "chrom_size_file_checksum",
                    "chrom_size_file_bed",
                    "chrom_size_file_bed_checksum",
                    "chrom_size_file_bed_index",
                    "chrom_size_file_bed_index_checksum",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(GeneSet)
class GeneSetAdmin(VersionAdmin):
    list_display = ("name", "collection", "subcollection", "subset", "reference_url")
    search_fields = ("name", "collection", "subcollection", "subset")
    list_filter = ("collection", "subcollection", "subset")
