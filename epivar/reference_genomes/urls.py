from django.urls import path
from . import views

urlpatterns = [
    # Reference Genomes
    path("reference-genomes/", views.ReferenceGenomeListView.as_view(), name="reference-genome-list"),
    path("reference-genomes/<int:pk>/", views.ReferenceGenomeDetailView.as_view(), name="reference-genome-detail"),

    # Genomic Features
    path("genomic-features/", views.GenomicFeatureListView.as_view(), name="genomic-feature-list"),
    path("genomic-features/data/", views.GenomicFeatureDataView.as_view(), name="genomic-feature-data"),
    path("genomic-features/<int:pk>/", views.GenomicFeatureDetailView.as_view(), name="genomic-feature-detail"),

    # Gene Sets
    path("gene-sets/", views.GeneSetListView.as_view(), name="gene-set-list"),
    path("gene-sets/data/", views.GeneSetDataView.as_view(), name="gene-sets-data"),
    path("gene-sets/<int:pk>/", views.GeneSetDetailView.as_view(), name="gene-set-detail"),
]
