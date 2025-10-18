import plotly.express as px
import numpy as np
import pandas as pd

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView, DetailView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect, reverse

from .tasks import gsea_task, loa_task, soa_task
from .forms import GSEAform, LOAForm, SOAForm
from .utils import _clean_gsea_table
from .plots import bubble_plot
from .models import GSEA, LOA, SOA


class AnalysesList(LoginRequiredMixin, ListView):
    model = GSEA
    template_name = "analyses/analyses_list.html"

    def get_queryset(self):
        """Limit queryset so only the submitter can delete their own analyses."""
        qs = super().get_queryset()
        return qs.filter(submitter=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Add category field for template logic
        gsea = GSEA.objects.filter(submitter=user).order_by("created_at")
        for obj in gsea:
            obj.category = "GSEA"

        loa = LOA.objects.filter(submitter=user).order_by("created_at")
        for obj in loa:
            obj.category = "LOA"

        soa = SOA.objects.filter(submitter=user).order_by("created_at")
        for obj in soa:
            obj.category = "SOA"

        context["analyses"] = [*list(gsea), *list(loa), *list(soa)]
        return context


class GSEAView(LoginRequiredMixin, CreateView):
    model = GSEA
    form_class = GSEAform
    template_name = "analyses/gsea_submission_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_name"] = "Gene-set Enrichment Analysis (GSEA)"
        return context

    def form_valid(self, form):
        gsea = form.save(commit=False)
        gsea.submitter = self.request.user
        gsea.save()

        gsea_task.delay_on_commit(gsea.id, gsea.universe)
        messages.success(self.request, "GSEA analysis has been submitted successfully!")
        return redirect("submitted-analyses")


class GSEADetailView(LoginRequiredMixin, DetailView):
    model = GSEA
    template_name = "analyses/gsea_detail.html"
    context_object_name = "gsea"

    def get_queryset(self):
        return super().get_queryset().filter(submitter=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gsea = self.object

        results = gsea.results or {}
        df = pd.DataFrame.from_records(results.get("gsea", []))

        collections = []
        if not df.empty:
            for collection_name, sub_df in df.groupby("Collection"):
                # Clean & filter table
                sub_df = _clean_gsea_table(
                    sub_df, correction_method=gsea.correction_method
                )
                sub_df = sub_df[sub_df["Adjusted P-value"] <= gsea.significance_level]

                if not sub_df.empty:
                    # Convert Term to clickable link
                    sub_df["Term"] = sub_df.apply(
                        lambda row: f'<a href="{reverse("gene-set-detail", args=[row["gene_set_id"]])}">{row["Term"]}</a>',
                        axis=1,
                    )
                    sub_df = sub_df.drop("gene_set_id", axis=1)
                    plot_html = bubble_plot(sub_df.iloc[:50])
                else:
                    plot_html = "<p>No significant results to plot</p>"

                sub_df.columns = [n.capitalize() for n in sub_df.columns]
                collections.append(
                    {
                        "name": collection_name,
                        "table_html": sub_df.to_html(
                            classes=[
                                "datatable",
                                "table",
                                "table-striped",
                                "table-hover",
                                "table-sm",
                            ],
                            index=False,
                            escape=False,
                            border=0,
                            table_id=f"table-{collection_name}",
                        ),
                        "plot_html": plot_html,
                    }
                )

        context.update(
            {
                "title": f"GSEA: {gsea.title}",
                "collections": collections,
                "intersection_stats": results.get("intersection_stats", {}),
                "metadata": {
                    "creation_date": gsea.created_at,
                    "reference_genome": gsea.reference_genome,
                    "foreground": gsea.foreground,
                    "background": gsea.background,
                    "annotated_foreground": gsea.annotated_foreground,
                    "annotated_background": gsea.annotated_background,
                    "universe_type": gsea.universe,
                    "minimum_overlap": gsea.minimum_overlap_required,
                    "significance_level": gsea.significance_level,
                    "correction_method": gsea.correction_method,
                    "same_strandedness": gsea.require_same_strandedness,
                },
            }
        )
        return context


class GSEADeleteView(LoginRequiredMixin, DeleteView):
    model = GSEA
    template_name = "analyses/confirm_delete.html"
    success_url = reverse_lazy("submitted-analyses")

    def get_queryset(self):
        """
        Limit the queryset so only the submitter can delete their own analyses.
        """
        qs = super().get_queryset()

        return qs.filter(submitter=self.request.user)


class LOAView(LoginRequiredMixin, CreateView):
    model = LOA
    form_class = LOAForm
    template_name = "analyses/loa_submission_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_name"] = "Locus Overlap Analysis (LOA)"
        return context

    def form_valid(self, form):
        loa = form.save(commit=False)
        loa.submitter = self.request.user

        loa.save()
        form.save_m2m()  # save ManyToMany selections from the form

        loa_task.delay_on_commit(loa.id)
        messages.success(self.request, "LOA analysis has been submitted successfully!")

        return redirect("submitted-analyses")


class LOADetailView(LoginRequiredMixin, DetailView):
    model = LOA
    template_name = "analyses/loa_detail.html"
    context_object_name = "loa"

    def get_queryset(self):
        return super().get_queryset().filter(submitter=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loa = self.object

        collections = []
        if loa.results:
            df = pd.DataFrame.from_records(loa.results)

            # Split per 'collection'
            for name, subdf in df.groupby("collection"):
                if subdf.empty:
                    continue

                fig_html = bubble_plot(subdf, hover="name", size="Foreground overlap")

                subdf["name"] = subdf.apply(
                    lambda
                        row: f'<a href="{reverse("genomic-feature-detail", args=[row["genomic_set_id"]])}">{row["name"]}</a>',
                    axis=1,
                )
                subdf = subdf.drop("genomic_set_id", axis=1)
                subdf.columns = [n.capitalize() for n in subdf.columns]

                table_html = subdf.to_html(
                    classes="table table-sm table-striped datatable",
                    index=False,
                    border=0,
                    escape=False,
                )

                collections.append(
                    {
                        "name": name,
                        "plot_html": fig_html,
                        "table_html": table_html,
                    }
                )

        context.update(
            {
                "title": f"LOA: {loa.title}",
                "collections": collections,
                "foreground": loa.foreground,
                "background": loa.background,
                "metadata": {
                    "creation_date": loa.created_at,
                    "permutations": loa.permutations,
                    "alternative": loa.alternative,
                    "lift_over_metrics": loa.lift_over_metrics,
                    "universe": " | ".join([x.name for x in loa.universe.all()]),
                },
            }
        )
        return context


class LOADeleteView(LoginRequiredMixin, DeleteView):
    model = LOA
    template_name = "analyses/confirm_delete.html"
    success_url = reverse_lazy("submitted-analyses")

    def get_queryset(self):
        """
        Limit the queryset so only the submitter can delete their own analyses.
        """
        qs = super().get_queryset()

        return qs.filter(
            submitter=self.request.user
        )  # assumes model has `submitter` FK


class SOAView(LoginRequiredMixin, CreateView):
    model = SOA
    form_class = SOAForm
    template_name = "analyses/soa_submission_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_name"] = "Study Overlap Analysis (SOA)"
        return context

    def form_valid(self, form):
        soa = form.save(commit=False)
        soa.submitter = self.request.user
        soa.save()

        soa_task.delay_on_commit(soa.id, soa.study_type)
        messages.success(self.request, "SOA analysis has been submitted successfully!")

        return redirect("submitted-analyses")


class SOADetailView(LoginRequiredMixin, DetailView):
    model = SOA
    template_name = "analyses/soa_detail.html"
    context_object_name = "soa"

    def get_queryset(self):
        return super().get_queryset().filter(submitter=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        soa = self.object

        context.update(
            {
                "title": f"SOA: {soa.title}",
                "results": soa.results,
                "metadata": {
                    "creation_date": soa.created_at,
                    "reference_genome": soa.reference_genome,
                    "foreground": soa.foreground,
                    "background": soa.background,
                    "significance_level": soa.significance_level,
                },
            }
        )

        return context


class SOADeleteView(LoginRequiredMixin, DeleteView):
    model = SOA
    template_name = "analyses/confirm_delete.html"
    success_url = reverse_lazy("submitted-analyses")

    def get_queryset(self):
        """
        Limit delete access to the submitter only.
        """
        return super().get_queryset().filter(submitter=self.request.user)
