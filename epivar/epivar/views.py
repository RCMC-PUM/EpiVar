from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page

from reference_genomes.models import GeneSet, GenomicFeature
from studies.models import IntegrationStatus
from studies.models import AssociationStudy, InteractionStudy, ProfilingStudy


def home(request):
    gene_sets_number = len(GeneSet.objects.all())
    gene_sets_number = round(gene_sets_number / 10**3, 0)

    studies_number = 0
    for dt in [AssociationStudy, InteractionStudy, ProfilingStudy]:
        studies_number += dt.objects.filter(integration_status=IntegrationStatus.PASSED).count()

    tracks_number = GenomicFeature.objects.all().count()
    context = {
        "gene_sets_number": gene_sets_number,
        "studies_number": studies_number,
        "tracks_number": tracks_number,
    }
    return render(request, "home.html", context)
