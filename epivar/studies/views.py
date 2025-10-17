import os
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from formtools.wizard.views import SessionWizardView
from django.views.generic import ListView, DetailView, CreateView, DeleteView
from pgvector.django import L2Distance
from django.urls import reverse_lazy

from reference_genomes.models import Assembly
from studies.models import RecordStatus, IntegrationStatus

from .models import (
    Project,
    AssociationStudy,
    InteractionStudy,
    ProfilingStudy,
    Embedding,
    IntegrationStatus,
)
from .forms import (
    BiosampleForm,
    SampleForm,
    PlatformForm,
    PhenotypeForm,
    InvestigationForm,
    DataForm,
    DataStorageForm
)
from .forms import (
    ProjectForm,
    AssociationStudyForm,
    InteractionStudyForm,
    ProfilingStudyForm,
)
from .plots import plotly_html_from_json


# Create your views here.
def start_submission(request):
    return render(request, "studies/start_submission.html", {})


class CreateProject(LoginRequiredMixin, CreateView):
    model = Project
    template_name = "studies/create_project.html"
    form_class = ProjectForm

    def form_valid(self, form):
        project = form.save(commit=False)
        project.submitter = self.request.user
        project.save()

        messages.success(
            self.request, f"New Project - {project.id} has been created successfully!"
        )
        return redirect("submitted-studies")


ASSOCIATION_STUDY_FORMS = [
    ("association_study", AssociationStudyForm),
    ("biosample", BiosampleForm),
    ("sample", SampleForm),
    ("platform", PlatformForm),
    ("phenotype", PhenotypeForm),
    ("investigation_model", InvestigationForm),
    ("raw_data_storage", DataStorageForm),
    ("submitted_data", DataForm),
]

INTERACTION_STUDY_FORMS = [
    ("interaction_study", InteractionStudyForm),
    ("biosample", BiosampleForm),
    ("sample", SampleForm),
    ("platform", PlatformForm),
    ("phenotype", PhenotypeForm),
    ("investigation_model", InvestigationForm),
    ("raw_data_storage", DataStorageForm),
    ("submitted_data", DataForm),
]

PROFILING_STUDY_FORMS = [
    ("profiling_study", ProfilingStudyForm),
    ("biosample", BiosampleForm),
    ("sample", SampleForm),
    ("platform", PlatformForm),
    ("phenotype", PhenotypeForm),
    ("raw_data_storage", DataStorageForm),
    ("submitted_data", DataForm),
]

TEMPLATES = {
    name[0]: "studies/submission_form_step.html"
    for name in [
        *ASSOCIATION_STUDY_FORMS,
        *INTERACTION_STUDY_FORMS,
        *PROFILING_STUDY_FORMS,
    ]
}


class AssociationStudyWizard(LoginRequiredMixin, SessionWizardView):
    form_list = ASSOCIATION_STUDY_FORMS
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "studies", "submitted")
    )

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context["form_name"] = "Association study"
        return context

    def done(self, form_list, form_dict, **kwargs):
        study = form_dict["association_study"].save(commit=False)
        study.submitter = self.request.user

        for step_name, form in form_dict.items():
            if step_name == "association_study":
                continue

            instance = form.save()
            step_name = form.prefix
            setattr(study, step_name, instance)

        study.save()
        messages.success(
            self.request,
            f"Interaction Study - {study.study_id} - has been successfully submitted!",
        )
        return redirect("submitted-studies")


class InteractionStudyWizard(LoginRequiredMixin, SessionWizardView):
    form_list = INTERACTION_STUDY_FORMS
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "studies", "submitted")
    )

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context["form_name"] = "Interaction study"
        return context

    def done(self, form_list, form_dict, **kwargs):
        study = form_dict["interaction_study"].save(commit=False)
        study.submitter = self.request.user

        for step_name, form in form_dict.items():
            if step_name == "interaction_study":
                continue

            instance = form.save()
            step_name = form.prefix
            setattr(study, step_name, instance)

        study.save()
        messages.success(
            self.request,
            f"Interaction Study - {study.study_id} - has been successfully submitted!",
        )
        return redirect("submitted-studies")


class ProfilingStudyWizard(LoginRequiredMixin, SessionWizardView):
    form_list = PROFILING_STUDY_FORMS
    file_storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "studies", "submitted")
    )

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context["form_name"] = "Profiling study"
        return context

    def done(self, form_list, form_dict, **kwargs):
        study = form_dict["profiling_study"].save(commit=False)
        study.submitter = self.request.user

        for step_name, form in form_dict.items():
            if step_name == "profiling_study":
                continue

            instance = form.save()
            step_name = form.prefix
            setattr(study, step_name, instance)

        study.save()
        messages.success(
            self.request,
            f"Profiling Study - {study.study_id} - has been successfully submitted!",
        )
        return redirect("submitted-studies")


class StudiesView(ListView):
    template_name = "studies/studies_list.html"
    context_object_name = "studies"

    def get_queryset(self):
        profiling = ProfilingStudy.objects.filter(
            record_status=RecordStatus.ACTIVE,
            integration_status=IntegrationStatus.PASSED,
        )
        association = AssociationStudy.objects.filter(
            record_status=RecordStatus.ACTIVE,
            integration_status=IntegrationStatus.PASSED,
        )
        interaction = InteractionStudy.objects.filter(
            record_status=RecordStatus.ACTIVE,
            integration_status=IntegrationStatus.PASSED,
        )

        return [*profiling, *association, *interaction]


class UserStudiesView(LoginRequiredMixin, ListView):
    template_name = "studies/studies_list.html"
    context_object_name = "studies"

    def get_queryset(self):
        user = self.request.user

        profiling = ProfilingStudy.objects.filter(submitter=user)
        association = AssociationStudy.objects.filter(submitter=user)
        interaction = InteractionStudy.objects.filter(submitter=user)

        return [*profiling, *association, *interaction]


def build_progress_steps(study):
    """Function returns tuples representing interaction status for template rendering."""
    steps = [
        ("Submission received", True, False),
        (
            "Waiting for technical check",
            study.integration_status
            in [
                IntegrationStatus.PENDING,
                IntegrationStatus.RUNNING,
                IntegrationStatus.PASSED,
                IntegrationStatus.FAILED,
            ],
            False,
        ),
        (
            "Running technical check",
            study.integration_status
            in [
                IntegrationStatus.RUNNING,
                IntegrationStatus.PASSED,
                IntegrationStatus.FAILED,
            ],
            False,
        ),
    ]

    if study.integration_status == IntegrationStatus.PASSED:
        steps.append(("Technical check passed", True, False))
    elif study.integration_status == IntegrationStatus.FAILED:
        steps.append(("Technical check failed", True, True))

    return steps


def build_integration_message(study):
    """If integration status is FAILED or RUNNING return message."""
    if study.integration_status == IntegrationStatus.FAILED:
        return study.integration_task.traceback
    if study.integration_status == IntegrationStatus.RUNNING:  # ← fixed equality check
        return "Your submission is being processed, it might take up to several hours."
    return None


class StudyDetailMixin(LoginRequiredMixin, DetailView):
    slug_field = "study_id"
    slug_url_kwarg = "study_id"
    context_object_name = "study"

    # subclass should set e.g. "phenotypic_association_data" or "interaction_data" or  "profiling_data"
    dataset_accessor = None

    def similarity_search(self, limit: int = 5, **kwargs):
        ctx = super().get_context_data(**kwargs)

        emd = ctx["study"].embedding.embedding
        search = Embedding.objects.order_by(L2Distance("embedding", emd))

        studies = []
        for e in search:
            if e.pk == ctx["study"].embedding.id:
                # skip the current study itself
                continue

            study = None
            for model in (AssociationStudy, InteractionStudy, ProfilingStudy):
                try:
                    study = model.objects.get(embedding_id=e.pk)
                    break
                except model.DoesNotExist:
                    continue

            if study and study.integration_status == IntegrationStatus.PASSED:
                studies.append(study)

            if len(studies) >= limit:
                break

        return studies

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = ctx["study"].study_id

        ctx["progress_steps"] = build_progress_steps(ctx["study"])
        ctx["integration_message"] = build_integration_message(ctx["study"])

        if self.dataset_accessor not in [
            "phenotypic_association_data",
            "interaction_data",
            "profiling_data",
        ]:
            raise ValueError(
                f"dataset accessor should be either: phenotypic_association_data or interaction_data or profiling_data"
            )

        if (
            ctx["study"].integration_status == IntegrationStatus.PASSED
            and self.dataset_accessor
        ):
            datasets = (
                getattr(ctx["study"], self.dataset_accessor)
                .select_related("reference_genome")
                .all()
            )
            hg38 = datasets.filter(reference_genome__name=Assembly.HG38).first()

            ctx.update({"datasets": datasets})
            ctx.update(
                {
                    "qq": plotly_html_from_json(hg38.plots.get("qq")),
                    "mh": plotly_html_from_json(hg38.plots.get("mh")),
                    "an": plotly_html_from_json(hg38.plots.get("an")),
                    "vl": plotly_html_from_json(hg38.plots.get("vl"))
                }
            )

            ctx["similar_studies"] = self.similarity_search()
        return ctx


class AssociationStudyDetailView(StudyDetailMixin):
    model = AssociationStudy
    template_name = "studies/association_study_detail.html"
    dataset_accessor = "phenotypic_association_data"

    def get_object(self, queryset=None):
        return get_object_or_404(
            AssociationStudy.objects.select_related(
                "project",
                "submitter",
                "biosample",
                "sample",
                "platform",
                "phenotype",
                "investigation_model",
            ),
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )


class InteractionStudyDetailView(StudyDetailMixin):
    model = InteractionStudy
    template_name = "studies/interaction_study_detail.html"
    dataset_accessor = "interaction_data"

    def get_object(self, queryset=None):
        return get_object_or_404(
            InteractionStudy.objects.select_related(
                "project",
                "submitter",
                "biosample",
                "sample",
                "platform",
            ).prefetch_related(
                "interaction_data",
            ),
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )


class ProfilingStudyDetailView(StudyDetailMixin):
    model = InteractionStudy
    template_name = "studies/profiling_study_detail.html"
    dataset_accessor = "profiling_data"

    def get_object(self, queryset=None):
        return get_object_or_404(
            ProfilingStudy.objects.select_related(
                "project",
                "submitter",
                "biosample",
                "sample",
                "platform",
            ).prefetch_related(
                "profiling_data",
            ),
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )


class AssociationStudyDeleteView(DeleteView):
    model = AssociationStudy
    slug_field = "study_id"
    slug_url_kwarg = "study_id"
    template_name = "studies/study_confirm_delete.html"
    success_url = reverse_lazy("submitted-studies")

    def get_object(self, queryset=None):
        return get_object_or_404(
            AssociationStudy,
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )


class InteractionStudyDeleteView(DeleteView):
    model = InteractionStudy
    slug_field = "study_id"
    slug_url_kwarg = "study_id"
    template_name = "studies/study_confirm_delete.html"
    success_url = reverse_lazy("submitted-studies")

    def get_object(self, queryset=None):
        return get_object_or_404(
            InteractionStudy,
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )


class ProfilingStudyDeleteView(DeleteView):
    model = ProfilingStudy
    slug_field = "study_id"
    slug_url_kwarg = "study_id"
    template_name = "studies/study_confirm_delete.html"
    success_url = reverse_lazy("submitted-studies")

    def get_object(self, queryset=None):
        return get_object_or_404(
            ProfilingStudy,
            study_id=self.kwargs.get(self.slug_url_kwarg),
        )
