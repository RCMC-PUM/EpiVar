from django.urls import path
from .views import SOAView, SOADetailView, SOADeleteView, GSEAView, LOAView, LOADetailView, AnalysesList, GSEADetailView, GSEADeleteView, LOADeleteView

urlpatterns = [
    path("submitted_analyses", AnalysesList.as_view(), name="submitted-analyses"),

    # GSEA
    path("gsea/submit", GSEAView.as_view(), name="gsea-submission-form"),
    path("gsea/view/<int:pk>/", GSEADetailView.as_view(), name="gsea-detail-view"),
    path("gsea/delete/<int:pk>/", GSEADeleteView.as_view(), name="gsea-delete-view"),

    # LOA
    path("loa/submit/", LOAView.as_view(), name="loa-submission-form"),
    path("loa/<int:pk>/", LOADetailView.as_view(), name="loa-detail-view"),
    path("loa/<int:pk>/delete/", LOADeleteView.as_view(), name="loa-delete-view"),

    # SOA
    path("soa/submit/", SOAView.as_view(), name="soa-submission-form"),
    path("soa/<int:pk>/", SOADetailView.as_view(), name="soa-detail-view"),
    path("soa/<int:pk>/delete/", SOADeleteView.as_view(), name="soa-delete-view"),
]
