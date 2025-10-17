from django_addanother.widgets import AddAnotherWidgetWrapper
from django.forms import ModelForm, Textarea, EmailInput
from django_select2.forms import ModelSelect2Widget
from django.urls import reverse_lazy

from ontologies.models import AnatomicalStructure, CellType, Term, TermCategory
from .models import Project, AssociationStudy, InteractionStudy, ProfilingStudy
from .models import Biosample, Sample, Platform, Phenotype, Investigation, StudyData, DataStorage


class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ["title", "authors", "contact", "affiliation", "description"]
        widgets = {
            "title": Textarea(
                attrs={"class": "form-control", "placeholder": "Enter project title"}
            ),
            "authors": Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "List authors (comma separated)",
                }
            ),
            "contact": EmailInput(
                attrs={"class": "form-control", "placeholder": "Enter contact email"}
            ),
            "affiliation": Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Institution or organization",
                }
            ),
            "description": Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Brief project description...",
                    "rows": 4,
                }
            ),
        }
        labels = {
            "tittle": "Project Title",
            "authors": "Authors",
            "contact": "Contact Email",
            "affiliation": "Affiliation",
            "description": "Description",
        }


study_form_fields = [
    "project",
    "title",
    "reference",
    "overall_description",
    "sample_processing_description",
    "data_processing_description",
]

study_form_widgets = {
    "overall_description": Textarea(
        attrs={"rows": 4, "maxlength": 1000, "data-counter": "true"}
    ),
    "sample_processing_description": Textarea(
        attrs={"rows": 4, "maxlength": 1000, "data-counter": "true"}
    ),
    "data_processing_description": Textarea(
        attrs={"rows": 4, "maxlength": 1000, "data-counter": "true"}
    ),
}

study_form_help_text = {
    "project": "Assign study to one of Your projects.",
    "title": "Short descriptive title of the association study.",
    "reference": "Reference e.g. PMID/DOI.",
    "overall_description": "Brief summary of the study design and objectives.",
    "sample_processing_description": "Description of how samples were collected, processed, and stored.",
    "data_processing_description": "Explanation of how data was processed and analyzed.",
}


class AssociationStudyForm(ModelForm):
    class Meta:
        model = AssociationStudy
        fields = study_form_fields
        help_texts = study_form_help_text
        widgets = study_form_widgets


class InteractionStudyForm(ModelForm):
    class Meta:
        model = InteractionStudy
        fields = [*study_form_fields, "interaction_type"]
        help_texts = study_form_help_text
        widgets = study_form_widgets


class ProfilingStudyForm(ModelForm):
    class Meta:
        model = ProfilingStudy
        fields = study_form_fields
        help_texts = study_form_help_text
        widgets = study_form_widgets


class BiosampleForm(ModelForm):
    class Meta:
        model = Biosample
        fields = "__all__"
        widgets = {
            "tissue": ModelSelect2Widget(
                model=AnatomicalStructure,
                search_fields=["label__icontains"],
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Search for tissue type ...",
                },
            ),
            "cell": ModelSelect2Widget(
                model=CellType,
                search_fields=["label__icontains"],
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Search for cell type ...",
                },
                dependent_fields={"cell": "cell_types"},
            ),
            "cell_line": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for cell line  ...",
                        "data-field-name": "cell_line",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.CELL_LINE}
                )
            ),
            "analyte": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for analyte type  ...",
                        "data-field-name": "analyte",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.ANALYTE}
                ),
            ),
        }
        help_texts = {
            "tissue": "Ontology describing sample tissue of origin, e.g., Blood.",
            "cell": "Ontology describing sample cell of origin, e.g., Lymphocyte.",
            "analyte": "Ontology describing analyte type, e.g., DNA or RNA.",
        }


class SampleForm(ModelForm):
    class Meta:
        model = Sample
        fields = ["sample_size", "replication_type"]
        help_texts = {
            "sample_size": "Number of individual samples in the experiment.",
            "replication_type": "Type of replication, e.g., biological or technical.",
        }


class DataStorageForm(ModelForm):
    class Meta:
        model = DataStorage
        fields = ["raw_data_storage", "raw_data_accession_number"]
        help_texts = {
            "raw_data_storage": "Raw data holder e.g. GEO",
            "raw_data_accession_number": "Raw data accession number e.g GSE222927"
        }


class PlatformForm(ModelForm):
    class Meta:
        model = Platform
        fields = "__all__"
        widgets = {
            "platform": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for platform type ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.PLATFORM}
                ),
            ),
            "assay": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for assay type ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.ASSAY}
                ),
            ),
            "target": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for target type ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.TARGET}
                ),
            ),
        }
        help_texts = {
            "platform": "Platform used for measurement, e.g., Illumina, ONP.",
            "assay": "Type of assay performed, e.g., ATAC-seq, ChIP-seq.",
            "target": "Specific target of the assay, e.g H3K27ac, DNAm.",
        }


class PhenotypeForm(ModelForm):
    class Meta:
        model = Phenotype
        fields = "__all__"
        widgets = {
            "hpo": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for HPO tag ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.PHENOTYPE}
                ),
            )
        }
        help_texts = {
            "hpo": "Human Phenotype Ontology (HPO) term describing the phenotype."
        }


class InvestigationForm(ModelForm):
    class Meta:
        model = Investigation
        fields = ["investigation_model", "statistical_test", "effect_size_metric"]
        widgets = {
            "investigation_model": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for ontology ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.INVESTIGATION_MODEL}
                ),
            ),
            "statistical_test": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for ontology ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.STATISTICAL_TEST}
                ),
            ),
            "effect_size_metric": AddAnotherWidgetWrapper(
                ModelSelect2Widget(
                    model=Term,
                    search_fields=["label__icontains"],
                    attrs={
                        "data-minimum-input-length": 0,
                        "data-placeholder": "Search for ontology ...",
                    },
                ),
                add_related_url=reverse_lazy(
                    "add-term", kwargs={"category": TermCategory.EFFECT_SIZE_METRIC}
                ),
            ),
        }
        help_texts = {
            "investigation_model": "Experimental or computational model used in the investigation.",
            "statistical_test": "Statistical test applied, e.g., t-test, ANOVA.",
            "effect_size_metric": "Metric used to report effect size, e.g., Cohen's d, Odds Ratio.",
        }


class DataForm(ModelForm):
    class Meta:
        model = StudyData
        fields = ["reference_genome", "data"]
        help_texts = {
            "reference_genome": "Reference genome version used, e.g., GRCh38.",
            "data": "Submitted dataset or file associated with the study.",
        }
