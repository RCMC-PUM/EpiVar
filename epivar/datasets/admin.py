from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import AssociationData, InteractionData, ProfilingData


class BaseDataAdmin(VersionAdmin):
    list_display = ("study__study_id", "reference_genome", "created_at", "updated_at")
    readonly_fields = (
        "data_conversion_metrics",
        "data_checksum",
        "data_index_checksum",
    )
    search_fields = ("study__study_id",)


@admin.register(AssociationData)
class PhenotypicAssociationDataAdmin(BaseDataAdmin):
    pass


@admin.register(InteractionData)
class PhenotypicAssociationDataAdmin(BaseDataAdmin):
    pass


@admin.register(ProfilingData)
class PhenotypicAssociationDataAdmin(BaseDataAdmin):
    pass
