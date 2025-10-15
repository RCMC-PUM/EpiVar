import os
import math
import tempfile
import pandas as pd
import numpy as np
import pybedtools
import gseapy as gp

from django.apps import apps
from celery import shared_task
from django.core.files import File
from django.shortcuts import reverse
from scipy.stats import fisher_exact
from django_celery_results.models import TaskResult
from django.core.exceptions import ValidationError

from reference_genomes.models import GeneSet, GeneSetCollection
from datasets.models import AssociationData, InteractionData, ProfilingData

from studies.models import (
    AssociationStudy, InteractionStudy, ProfilingStudy,
    IntegrationStatus, RecordStatus
)
from .utils import _clean_loa_table, _clean_gsea_table
from .data_models import BEDRecord, GeneListRecord, validate_file


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def _annotate_bed(
        bed_file, reference, feature_type: str = "gene",
        n_closest: int = 1, max_distance: int = 0,
        require_same_strandedness: bool = False
):
    """Annotate a BED file against the reference GFF."""
    gff = pybedtools.BedTool(reference.annotations_file.path)
    bed = pybedtools.BedTool(bed_file.path)

    annotations = bed.sort(header=True).closest(
        gff, d=True, k=n_closest, s=require_same_strandedness
    ).to_dataframe()

    bed_headers = pd.read_table(bed_file.path, nrows=1).columns.tolist()
    gff_headers = [
        "seqname", "source", "feature", "feature_start", "feature_end",
        "feature_score", "feature_strand", "frame", "attributes",
    ]
    annotations.columns = [*bed_headers, *gff_headers, "distance"]
    annotations = annotations[
        [*bed_headers, "seqname", "feature_start", "feature_end", "feature_strand",
         "feature", "attributes", "distance"]
    ]

    annotations = annotations[
        (annotations.feature == feature_type) & (annotations.distance <= max_distance)
        ]

    if annotations.empty:
        raise ValueError("Cannot annotate provided data, returned empty frame, try to relax annotation conditions.")

    return annotations


def _extract_genes(annotations):
    """Extract unique gene names from attributes."""
    return (
        annotations["attributes"]
        .str.extract(r"Name=([^;]+)")
        .dropna()[0]
        .unique()
        .tolist()
    )


def _save_annotations(annotations, instance, field_name, original_name):
    """Save annotated DataFrame to instance FileField."""
    with tempfile.NamedTemporaryFile(suffix=".bed", delete=False) as tmp:
        annotations.to_csv(tmp.name, sep="\t", index=False)
        getattr(instance, field_name).save(
            f"{os.path.basename(original_name)}.annotated.bed",
            File(open(tmp.name, "rb")),
            save=False
        )


def _fallback_background(reference, feature_type: str = "gene"):
    """Use all annotated genes if no background provided."""
    gff = pybedtools.BedTool(reference.annotations_file.path).to_dataframe()
    gff = gff[gff.feature == feature_type]
    return gff["attributes"].str.extract(r"Name=([^;]+)").dropna()[0].unique().tolist()


def _attach_task(instance, task_id):
    """Attach Celery task result to instance."""
    instance.task = TaskResult.objects.get(task_id=task_id)
    instance.save(update_fields=["task"])
    return instance


def _validate_inputs(instance, input_type: str):
    """Validate input files depending on type."""
    record_type = BEDRecord if input_type == "genomic_intervals" else GeneListRecord
    validate_file(instance.foreground.path, record_type)

    if hasattr(instance, "background") and instance.background:
        validate_file(instance.background.path, record_type)


def _compute_intersection_with_reference(instance, reference):
    """Compute intersection statistics with reference genome."""
    reference_bed = pybedtools.BedTool(reference.chrom_size_file_bed.path)
    foreground_bed = pybedtools.BedTool(instance.foreground.path)

    fg_intersection = foreground_bed.intersect(reference_bed, u=True).count()
    fg_total = foreground_bed.count()
    fg_fraction = fg_intersection / fg_total

    if instance.background:
        background_bed = pybedtools.BedTool(instance.background.path)
        fg_bg_intersection = foreground_bed.intersect(background_bed, header=True).count()
        if fg_bg_intersection < fg_total:
            raise ValidationError(f"Foreground is not a subset of background! Intersection: {fg_bg_intersection}, but total: {fg_total}")

        bg_intersection = background_bed.intersect(reference_bed, u=True).count()
        bg_total = background_bed.count()
        bg_fraction = bg_intersection / bg_total
    else:
        bg_intersection, bg_total, bg_fraction = None, None, None

    return {
        "foreground_intersection": fg_intersection,
        "foreground_total": fg_total,
        "foreground_fraction": fg_fraction,
        "background_intersection": bg_intersection,
        "background_total": bg_total,
        "background_fraction": bg_fraction,
    }


def parse_gene_list(path_to_file):
    """Parse file into unique gene list."""
    with open(path_to_file, "r") as handle:
        genes = [line.strip() for line in handle]
    return list(set(genes))


# =========================================================
# STEP FUNCTIONS (PIPELINE STAGES)
# =========================================================

def step_annotate_and_extract_foreground(instance, reference):
    """Annotate foreground and extract genes."""
    fg_annotations = _annotate_bed(
        instance.foreground, reference,
        n_closest=1,
        max_distance=instance.minimum_overlap_required,
        require_same_strandedness=instance.require_same_strandedness
    )
    _save_annotations(fg_annotations, instance, "annotated_foreground", instance.foreground.name)
    return _extract_genes(fg_annotations)


def step_annotate_and_extract_background(instance, reference):
    """Annotate background (if any) or fallback to universe."""
    if instance.background:
        bg_annotations = _annotate_bed(
            instance.background, reference,
        )
        _save_annotations(bg_annotations, instance, "annotated_background", instance.background.name)
        return _extract_genes(bg_annotations)
    else:
        return _fallback_background(reference)


def run_gsea_enrichment(fg_genes, bg_genes: list, universe: str | None = None):
    """Run enrichment across all gene set collections."""
    eps = np.nextafter(0, 1)
    results = []

    collections = [c for c in GeneSetCollection if c == universe] if universe else GeneSetCollection

    for collection in collections:
        gene_sets_in_collection = {
            obj.name: obj.genes["genes"]
            for obj in GeneSet.objects.filter(collection=collection)
        }
        mapping = {
            obj.name: obj.id
            for obj in GeneSet.objects.filter(collection=collection)
        }

        res = gp.enrich(
            gene_list=fg_genes,
            background=bg_genes,
            gene_sets=gene_sets_in_collection,
            outdir=None,
        ).results

        if isinstance(res, pd.DataFrame):
            res["Collection"] = collection.label
            res["gene_set_id"] = res["Term"].map(mapping)
            results.append(res)
        else:
            print(f"Error for {collection}")

    results = pd.concat(results)
    results["Overlap fraction"] = results["Overlap"].apply(
        lambda x: int(x.split("/")[0]) / int(x.split("/")[1])
    )
    return results


def safe_fisher(contingency, alternative):
    corrected = np.array(contingency, dtype=float) + 0.5
    odds_ratio, pvalue = fisher_exact(corrected, alternative=alternative)

    if math.isnan(odds_ratio) or math.isinf(odds_ratio):
        odds_ratio = None

    return odds_ratio, pvalue


def locus_overlap_with_bg(fg, bg, ref, alternative="two-sided") -> dict:
    """
    Locus overlap analysis when a background is provided.
    """
    fg = pybedtools.BedTool(fg) if not isinstance(fg, pybedtools.BedTool) else fg
    bg = pybedtools.BedTool(bg) if not isinstance(bg, pybedtools.BedTool) else bg
    ref = pybedtools.BedTool(ref) if not isinstance(ref, pybedtools.BedTool) else ref

    n_fg = len(fg)
    n_bg = len(bg)

    fg_overlap = len(fg.intersect(ref, u=True))
    bg_overlap = len(bg.intersect(ref, u=True))

    contingency = [
        [fg_overlap, n_fg - fg_overlap],
        [bg_overlap, n_bg - bg_overlap],
    ]

    fg_frac = fg_overlap / n_fg if n_fg > 0 else 0
    bg_frac = bg_overlap / n_bg if n_bg > 0 else 0
    ratio = fg_frac / bg_frac if bg_frac > 0 else 0

    odds_ratio, pvalue = safe_fisher(contingency, alternative)

    return {
        "Foreground_total": n_fg,
        "Background total": n_bg,
        "Foreground overlap": fg_overlap,
        "Background overlap": bg_overlap,
        "Foreground to background ratio": ratio,
        "Odds Ratio": odds_ratio,
        "P-value": pvalue,
    }


def locus_overlap_with_shuffle(fg, ref, genome, permutations=1000, alternative="two-sided") -> dict:
    """
    Locus overlap analysis when no background is provided.
    Uses shuffled foreground intervals as null background.
    """
    fg = pybedtools.BedTool(fg) if not isinstance(fg, pybedtools.BedTool) else fg
    ref = pybedtools.BedTool(ref) if not isinstance(ref, pybedtools.BedTool) else ref

    n_fg = len(fg)
    fg_overlap = len(fg.intersect(ref, u=True))

    shuffle_overlaps = [
        len(fg.shuffle(g=genome).intersect(ref, u=True))
        for _ in range(permutations)
    ]

    mean_bg_overlap = np.mean(shuffle_overlaps)
    contingency = [
        [fg_overlap, n_fg - fg_overlap],
        [mean_bg_overlap, n_fg - mean_bg_overlap],
    ]

    fg_frac = fg_overlap / n_fg if n_fg > 0 else 0
    bg_frac = mean_bg_overlap / n_fg if n_fg > 0 else 0
    ratio = fg_frac / bg_frac if bg_frac > 0 else 0

    odds_ratio, pvalue = safe_fisher(contingency, alternative)

    return {
        "Foreground_total": n_fg,
        "Background total": n_fg,  # foreground reused as "universe"
        "Foreground overlap": fg_overlap,
        "Background overlap": mean_bg_overlap,
        "Foreground to background ratio": ratio,
        "Odds Ratio": odds_ratio,
        "P-value": pvalue,
    }


def _filter_studies(data_class, request, category, pval: float | None = None):
    ref = request.reference_genome
    alpha = request.significance_level
    request_bed = pybedtools.BedTool(request.foreground.path)
    total = request_bed.count()

    results = []
    for study_data in data_class.objects.filter(reference_genome=ref).all():
        ovp = pybedtools.BedTool(study_data.data.path).intersect(request_bed, u=True, header=True)

        if pval:
            ovp = ovp.to_dataframe(disable_auto_names=True)
            ovp = ovp[ovp.FDR <= alpha].shape[0]
        else:
            ovp = ovp.count()

        fraction = ovp / total
        study = study_data.study
        if isinstance(study, AssociationStudy):
            link = reverse("association-study-detail", args=[study.study_id])
        elif isinstance(study, InteractionStudy):
            link = reverse("interaction-study-detail", args=[study.study_id])
        elif isinstance(study, ProfilingStudy):
            link = reverse("profiling-study-detail", args=[study.study_id])
        else:
            link = None

        record = {
            "Study": study.study_id,
            "Total": total,
            "Ovp": ovp,
            "Fraction": fraction,
            "Link": link,
            "Category": category,
        }
        results.append(record)

    return results


# =========================================================
# TASKS
# =========================================================

@shared_task(bind=True)
def gsea_task(self, gsea_id, universe=None):
    """Main GSEA pipeline task."""
    GSEA = apps.get_model("analyses", "GSEA")
    instance = GSEA.objects.get(id=gsea_id)

    instance = _attach_task(instance, self.request.id)
    _validate_inputs(instance, instance.input_type)

    intersection_stats = None
    if instance.input_type == "genomic_intervals":
        reference = instance.reference_genome
        intersection_stats = _compute_intersection_with_reference(instance, reference)

        fg_genes = step_annotate_and_extract_foreground(instance, reference)
        bg_genes = step_annotate_and_extract_background(instance, reference)

        instance.save(update_fields=["annotated_foreground", "annotated_background"])
    else:
        fg_genes = parse_gene_list(instance.foreground.path)
        if instance.background:
            bg_genes = parse_gene_list(instance.background.path)
        else:
            bg_genes = _fallback_background(instance.reference_genome)

    results = run_gsea_enrichment(fg_genes, bg_genes, universe)
    results = _clean_gsea_table(results, instance.correction_method)

    results = results[results["Adjusted P-value"] <= instance.significance_level]
    results = results.to_dict(orient="records")

    instance.results = {"intersection_stats": intersection_stats, "gsea": results}
    instance.save(update_fields=["results"])


@shared_task(bind=True)
def loa_task(self, loa_id):
    LOA = apps.get_model("analyses", "LOA")
    instance = LOA.objects.get(id=loa_id)
    instance = _attach_task(instance, self.request.id)

    validate_file(instance.foreground.path, BEDRecord)
    if instance.background:
        validate_file(instance.background.path, BEDRecord)

    fg = pybedtools.BedTool(instance.foreground.path)
    results = []

    for collection in instance.universe.all():
        for genomic_set in collection.features.all():
            try:
                ref = genomic_set.file.path
                stats = {"collection": collection.name, "name": genomic_set.name, "genomic_set_id": genomic_set.id}

                if instance.background:
                    bg = pybedtools.BedTool(instance.background.path)
                    stats.update(
                        locus_overlap_with_bg(fg, bg, ref, instance.alternative)
                    )
                else:
                    stats.update(
                        locus_overlap_with_shuffle(
                            fg,
                            ref,
                            instance.reference_genome.chrom_size_file.path,
                            permutations=instance.permutations,
                            alternative=instance.alternative,
                        )
                    )

                results.append(stats)

            except Exception as e:
                results.append({"name": genomic_set.name, "error": str(e)})

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df = _clean_loa_table(df, instance.correction_method)
    df = df[df["Adjusted P-value"] <= instance.significance_level]

    # And now to json
    instance.results = df.to_dict(orient="records")
    instance.save(update_fields=["results"])


@shared_task(bind=True)
def soa_task(self, soa_id):
    """Main SOA pipeline task."""
    SOA = apps.get_model("analyses", "SOA")
    instance = SOA.objects.get(id=soa_id)

    instance = _attach_task(instance, self.request.id)
    validate_file(instance.foreground.path, BEDRecord)

    association_data = _filter_studies(AssociationData, instance, "Association data", instance.significance_level)
    interaction_data = _filter_studies(InteractionData, instance, "Interaction data", instance.significance_level)
    profiling_data = _filter_studies(ProfilingData, instance, "Profiling data")

    results = [*association_data, *interaction_data, *profiling_data]
    instance.results = results
    instance.save(update_fields=["results"])
