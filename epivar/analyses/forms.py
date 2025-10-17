from django.forms.widgets import RadioSelect
from django_select2.forms import ModelSelect2MultipleWidget

from reference_genomes.models import GenomicFeatureCollection
from .models import GSEA, LOA, SOA
from django import forms


class GSEAform(forms.ModelForm):
    class Meta:
        model = GSEA
        fields = [
            "title",
            "input_type",
            "reference_genome",
            "foreground",
            "background",
            "universe",
            "n_closest",
            "max_absolute_distance",
            "require_same_strandedness",
            "significance_level",
            "correction_method",
        ]
        widgets = {
            # radio buttons for input_type
            "input_type": forms.RadioSelect(choices=GSEA.INPUT_TYPE_CHOICES),
        }
        help_texts = {
            "title": "Short analysis description.",
            "input_type": "Choose whether your input data represents genomic intervals (BED) or gene names (list).",
            "reference_genome": "Select the reference genome for this analysis.",
            "foreground": "Upload dataset representing the test set.",
            "background": "Upload dataset representing the background set.",
            "universe": "Optional: Constrain the universe of gene sets considered in the analysis to specific collections.",
            "n_closest": "Optional: Number of closest features to consider (1–10).",
            "max_absolute_distance": "Optional: Maximum allowed distance (in bases) between features (0–5000).",
            "require_same_strandedness": "Optional: Check this to consider strand orientation.",
            "significance_level": "P-value threshold (e.g., 0.05) for statistical significance.",
            "correction_method": "Choose a multiple testing correction method (e.g., Bonferroni, FDR).",
        }


class LOAForm(forms.ModelForm):
    class Meta:
        model = LOA
        fields = [
            "title",
            "reference_genome",
            "foreground",
            "background",
            "universe",
            "minimum_overlap_required",
            "alternative",
            "significance_level",
            "correction_method",
            "permutations",
        ]

        widgets = {
            "universe": ModelSelect2MultipleWidget(
                model=GenomicFeatureCollection,
                search_fields=["name__icontains"],
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Search for specific universes ...",
                    "data-maximum-selection-length": 5,
                },
            ),
            "permutations": RadioSelect(  # radio button widget
                choices=[(10, 10), (25, 25), (50, 50)]  # 10, 25, 50
            ),
        }

        help_texts = {
            "title": "Short analysis description.",
            "reference_genome": "Select the reference genome for this analysis.",
            "foreground": "Upload dataset representing the test set.",
            "background": "Upload dataset representing the background set.",
            "universe": "Define the universe of genomic tracks (up to 5) considered in the analysis.",
            "minimum_overlap_required": "Minimum number of bases/regions required for an overlap to count.",
            "alternative": "Defines the alternative hypothesis, one-side alternatives provides larger statistical power.",
            "significance_level": "p-value threshold (e.g., 0.05) for statistical significance.",
            "correction_method": "Choose a multiple testing correction method (e.g., Bonferroni, FDR).",
            "permutations": "Select the number of permutations to run (10–50). Larger values might provide more reliable estimates but require more time.",
        }


class SOAForm(forms.ModelForm):
    class Meta:
        model = SOA
        fields = [
            "title",
            "reference_genome",
            "foreground",
            "study_type",
            "significance_level"
        ]

        help_texts = {
            "title": "Short analysis description.",
            "reference_genome": "Select the reference genome for this analysis.",
            "foreground": "Upload dataset representing the test set.",
            "study_type": "Type of studies to search",
            "significance_level": "p-value threshold (e.g., 0.05) for statistical significance. Applicable only for Asscoation and Interaction studies",
        }
