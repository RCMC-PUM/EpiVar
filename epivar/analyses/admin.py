from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import GSEA, LOA, SOA

admin.site.site_header = "EpiVar Admin Portal"
admin.site.site_title = "EpiVar Admin Portal"
admin.site.index_title = "EpiVar Admin Portal"


@admin.register(GSEA)
class GSEAAnalysisAdmin(VersionAdmin):
    readonly_fields = ("task",)


@admin.register(LOA)
class LOAAnalysisAdmin(VersionAdmin):
    readonly_fields = ("task",)


@admin.register(SOA)
class SOAAnalysisAdmin(VersionAdmin):
    readonly_fields = ("task",)
