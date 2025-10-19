from django.urls import path
from .views import (
    AnalysesList,
    SOAView,
    SOADetailView,
    SOADeleteView,
    SOAUpdateView,
    LOAView,
    LOADetailView,
    LOADeleteView,
    LOAUpdateView,
    GSEAView,
    GSEADetailView,
    GSEADeleteView,
    GSEAUpdateView,
)

urlpatterns = [
    path("submitted_analyses", AnalysesList.as_view(), name="submitted-analyses"),
    # GSEA
    path("gsea/submit", GSEAView.as_view(), name="gsea-submission-form"),
    path("gsea/view/<int:pk>/", GSEADetailView.as_view(), name="gsea-detail-view"),
    path("gsea/delete/<int:pk>/", GSEADeleteView.as_view(), name="gsea-delete-view"),
    path('gsea/<int:pk>/update/', GSEAUpdateView.as_view(), name='gsea-update-view'),
    # LOA
    path("loa/submit/", LOAView.as_view(), name="loa-submission-form"),
    path("loa/<int:pk>/", LOADetailView.as_view(), name="loa-detail-view"),
    path("loa/<int:pk>/delete/", LOADeleteView.as_view(), name="loa-delete-view"),
    path('loa/<int:pk>/update/', LOAUpdateView.as_view(), name='loa-update-view'),
    # SOA
    path("soa/submit/", SOAView.as_view(), name="soa-submission-form"),
    path("soa/<int:pk>/", SOADetailView.as_view(), name="soa-detail-view"),
    path("soa/<int:pk>/delete/", SOADeleteView.as_view(), name="soa-delete-view"),
    path('soa/<int:pk>/update/', SOAUpdateView.as_view(), name='soa-update-view'),
]
