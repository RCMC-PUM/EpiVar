from django.views.generic import ListView, DetailView

from django.http import JsonResponse
from django.views import View
from django.db.models import Q
from django.shortcuts import reverse

from .models import ReferenceGenome, GenomicFeature, GeneSet


# ReferenceGenome
class ReferenceGenomeListView(ListView):
    model = ReferenceGenome
    template_name = "reference_genomes/reference_genomes_list.html"
    context_object_name = "genomes"


class ReferenceGenomeDetailView(DetailView):
    model = ReferenceGenome
    template_name = "reference_genomes/reference_genomes_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        genome = self.object
        # Collect related chain files
        chains = list(genome.source_genome.all()) + list(genome.target_genome.all())
        context["chains"] = chains
        return context


class GenomicFeatureListView(ListView):
    model = GenomicFeature
    template_name = "reference_genomes/genomic_features_list.html"
    context_object_name = "features"

    def get_context_data(self, **kwargs):
        # Same as GeneSetListView: DataTables will load data via Ajax
        context = super().get_context_data(**kwargs)
        context["features"] = []
        return context


# GenomicFeature
class GenomicFeatureDataView(View):
    def get(self, request, *args, **kwargs):
        # DataTables params
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search_value = request.GET.get("search[value]", "")
        order_col = request.GET.get("order[0][column]", 0)
        order_dir = request.GET.get("order[0][dir]", "asc")

        # Columns must match the HTML <th> order in template
        columns = ["name", "description", "collection", "reference_genome", "id"]
        queryset = GenomicFeature.objects.all()

        # Filtering (search box)
        if search_value:
            queryset = queryset.filter(
                Q(name__icontains=search_value) |
                Q(description__icontains=search_value) |
                Q(reference_genome__name__icontains=search_value) |
                Q(collection__name__icontains=search_value)
            )

        total_records = GenomicFeature.objects.count()
        filtered_records = queryset.count()

        # Ordering
        order_column = columns[int(order_col)]
        if order_dir == "desc":
            order_column = "-" + order_column
        queryset = queryset.order_by(order_column)

        # Pagination
        queryset = queryset[start:start + length]

        # Build response
        data = []
        for feature in queryset:
            data.append({
                "id": feature.id,
                "name": feature.name,
                "collection": feature.collection.name,
                "description": feature.description,
                "reference_genome": (
                    feature.reference_genome.name if feature.reference_genome else ""
                ),
                "detail_url": reverse("genomic-feature-detail", args=[feature.id]),
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })


class GenomicFeatureDetailView(DetailView):
    model = GenomicFeature
    template_name = "reference_genomes/genomic_features_detail.html"


# GeneSet
class GeneSetListView(ListView):
    model = GeneSet
    template_name = "reference_genomes/gene_sets_list.html"
    context_object_name = "genesets"

    def get_context_data(self, **kwargs):
        # We don't actually need to send all rows anymore
        context = super().get_context_data(**kwargs)
        context["genesets"] = []  # empty list; DataTables will fill via Ajax
        return context


class GeneSetDataView(View):
    def get(self, request, *args, **kwargs):
        # DataTables params
        draw = int(request.GET.get("draw", 1))
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))
        search_value = request.GET.get("search[value]", "")
        order_col = request.GET.get("order[0][column]", 0)
        order_dir = request.GET.get("order[0][dir]", "asc")

        # Column map (must match DataTables "columns" list in template)
        columns = ["name", "collection", "subcollection", "systematic_name", "id"]

        queryset = GeneSet.objects.all()

        # Filtering (search box)
        if search_value:
            queryset = queryset.filter(
                Q(name__icontains=search_value) |
                Q(collection__icontains=search_value) |
                Q(subcollection__icontains=search_value) |
                Q(systematic_name__icontains=search_value)
            )

        total_records = GeneSet.objects.count()
        filtered_records = queryset.count()

        # Ordering
        order_column = columns[int(order_col)]
        if order_dir == "desc":
            order_column = "-" + order_column
        queryset = queryset.order_by(order_column)

        # Pagination
        queryset = queryset[start:start + length]

        # Build response
        # Build response
        data = []
        for gs in queryset:
            data.append({
                "id": gs.id,
                "name": gs.name,
                "collection": gs.collection,
                "subcollection": gs.subcollection,
                "systematic_name": gs.systematic_name,
                "detail_url": reverse("gene-set-detail", args=[gs.id])
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })


class GeneSetDetailView(DetailView):
    model = GeneSet
    template_name = "reference_genomes/gene_sets_detail.html"
