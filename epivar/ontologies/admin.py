from django.contrib import admin
from .models import AnatomicalStructure, CellType, Term


@admin.register(AnatomicalStructure)
class AnatomicalStructureAdmin(admin.ModelAdmin):
    list_display = ("obo_id", "label", "iri", "created_at", "updated_at")
    search_fields = ("obo_id", "label")


@admin.register(CellType)
class CellTypeAdmin(admin.ModelAdmin):
    list_display = ("obo_id", "label", "iri", "created_at", "updated_at")
    search_fields = ("obo_id", "label")
    list_filter = ("anatomical_structure",)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("obo_id", "label", "category", "iri", "created_at", "updated_at")
    search_fields = ("obo_id", "category", "label")
    list_filter = ("category",)
