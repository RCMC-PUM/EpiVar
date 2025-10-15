from django.urls import path

from .views import start_submission, UserStudiesView, CreateProject
from .views import (
    AssociationStudyDetailView,
    AssociationStudyWizard,
    ASSOCIATION_STUDY_FORMS,
)
from .views import (
    InteractionStudyDetailView,
    InteractionStudyWizard,
    INTERACTION_STUDY_FORMS,
)
from .views import StudiesView
from .views import ProfilingStudyDetailView, ProfilingStudyWizard, PROFILING_STUDY_FORMS
from .views import (
    AssociationStudyDeleteView,
    InteractionStudyDeleteView,
    ProfilingStudyDeleteView,
)


urlpatterns = [
    # Studies lists
    path("studies/", StudiesView.as_view(), name="studies-list"),
    path("submitted_studies/", UserStudiesView.as_view(), name="submitted-studies"),

    # Start submission
    path("start_submission/", start_submission, name="start-submission"),
    path("create_project/", CreateProject.as_view(), name="create-project"),

    # Association study
    path(
        "association_study/submit",
        AssociationStudyWizard.as_view(ASSOCIATION_STUDY_FORMS),
        name="submit-association-study",
    ),
    path(
        "association_study/<str:study_id>/",
        AssociationStudyDetailView.as_view(),
        name="association-study-detail",
    ),
    path(
        "association/<slug:study_id>/delete/",
        AssociationStudyDeleteView.as_view(),
        name="association-study-delete",
    ),
    # Interaction study
    path(
        "interaction_study/submit",
        InteractionStudyWizard.as_view(INTERACTION_STUDY_FORMS),
        name="submit-interaction-study",
    ),
    path(
        "interaction_study/<str:study_id>/",
        InteractionStudyDetailView.as_view(),
        name="interaction-study-detail",
    ),
    path(
        "interaction/<slug:study_id>/delete/",
        InteractionStudyDeleteView.as_view(),
        name="interaction-study-delete",
    ),
    # Profiling study
    path(
        "profiling_study/submit",
        ProfilingStudyWizard.as_view(PROFILING_STUDY_FORMS),
        name="submit-profiling-study",
    ),
    path(
        "profiling_study/<str:study_id>/",
        ProfilingStudyDetailView.as_view(),
        name="profiling-study-detail",
    ),
    path(
        "profiling/<slug:study_id>/delete/",
        ProfilingStudyDeleteView.as_view(),
        name="profiling-study-delete",
    ),
]
