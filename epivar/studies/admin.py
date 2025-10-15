from django.contrib import admin
from datasets.models import AssociationData, InteractionData, ProfilingData
from .models import (
    Project,
    Biosample,
    Investigation,
    Phenotype,
    Platform,
    Sample,
    StudyData,
    AssociationStudy,
    InteractionStudy,
    ProfilingStudy,
)


# Hidden models
class HiddenModelAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return False


admin.site.register(Platform, HiddenModelAdmin)
admin.site.register(Biosample, HiddenModelAdmin)
admin.site.register(Phenotype, HiddenModelAdmin)
admin.site.register(Investigation, HiddenModelAdmin)
admin.site.register(Sample, HiddenModelAdmin)


@admin.register(StudyData)
class StudyDataAdmin(HiddenModelAdmin):
    readonly_fields = ("metadata", "data_checksum")


# Project Model
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("project_id", "title", "submitter", "created_at")
    search_fields = ("project_id", "title", "submitter__email")


# Inlines
class AssociationDataInline(admin.StackedInline):
    model = AssociationData
    extra = 0
    max_num = 0
    exclude = ("plots",)


class InteractionDataInline(admin.StackedInline):
    model = InteractionData
    extra = 0
    max_num = 0
    exclude = ("plots",)


class ProfilingDataInline(admin.StackedInline):
    model = ProfilingData
    extra = 0
    max_num = 0
    exclude = ("plots",)


# Study Models
class BaseStudyAdmin(admin.ModelAdmin):
    list_display = (
        "study_id",
        "submitter",
        "reviewer",
        "created_at",
        "updated_at",
        "integration_status",
    )
    readonly_fields = ("integration_task", "preprocessed_data")
    search_fields = ("study_id", "submitter__username", "submitter__email")


@admin.register(AssociationStudy)
class AssociationStudyAdmin(BaseStudyAdmin):
    inlines = [AssociationDataInline]


@admin.register(InteractionStudy)
class InteractionStudyAdmin(BaseStudyAdmin):
    inlines = [InteractionDataInline]


@admin.register(ProfilingStudy)
class ProfilingStudyAdmin(BaseStudyAdmin):
    inlines = [ProfilingDataInline]
