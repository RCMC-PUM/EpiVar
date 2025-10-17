import os
import hashlib
import logging
import shutil
import tempfile

import pysam
import numpy as np
import pandas as pd
from django.apps import apps
from scipy.stats import norm
from celery import shared_task
from pybedtools import BedTool
from django.db import transaction
from django.core.cache import cache
from django.core.files.base import File
from django.core.exceptions import ValidationError
from sentence_transformers import SentenceTransformer
from statsmodels.stats.multitest import multipletests

from users.models import User
from datasets.models import DataTypes
from reference_genomes.models import Assembly, ChainFile
from reference_genomes.genomics import lift_over, lift_over_metrics, sort_index_bgzip
from datasets.data_models import (
    AssociationRecord,
    InteractionRecord,
    ProfilingRecord,
    validate_file,
)

from .plots import manhattan, qq, bar, violin
from .models import IntegrationStatus, Embedding, StudyData
from .utils import update_integration_status

logger = logging.getLogger(__name__)


@shared_task
def create_embeddings_task(
    model_name, instance_id, sentence_transformer_model="all-MiniLM-L6-v2"
):
    model_class = apps.get_model("studies", model_name)
    instance = model_class.objects.select_related("embedding").filter(id=instance_id)

    data = instance.first().overall_description
    data_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()
    cache_key = f"embedding:{sentence_transformer_model}:{data_hash}"

    embedding = cache.get(cache_key)
    if embedding is None:
        model = SentenceTransformer(sentence_transformer_model)
        embedding = model.encode(data, normalize_embeddings=True).tolist()
        cache.set(cache_key, embedding, timeout=None)

    emb_ = Embedding(
        text=data,
        embedding=embedding,
    )
    emb_.save()

    instance.embedding = emb_
    instance.update(embedding=emb_)


@shared_task(bind=True)
def init_integration_task(self, study_model, instance_id):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )


@shared_task(bind=True)
def initial_test_task(self, study_model, instance_id, record_type: str):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("submitted_data").get(
        id=instance_id
    )
    input_path = study_instance.submitted_data.data.path

    match record_type:
        case "association_record":
            validate_file(input_path, AssociationRecord)
        case "profiling_record":
            validate_file(input_path, ProfilingRecord)
        case "interaction_record":
            validate_file(input_path, InteractionRecord)
        case _:
            raise ValidationError(f"{record_type} not supported!")


@shared_task(bind=True)
def intersection_task(self, study_model, instance_id):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("submitted_data").get(
        id=instance_id
    )

    chrom_sizes = BedTool(
        study_instance.submitted_data.reference_genome.chrom_size_file_bed.path
    )
    submitted_data = BedTool(study_instance.submitted_data.data.path)
    intersection = submitted_data.intersect(chrom_sizes, u=True, header=True)

    sc = submitted_data.count()
    ic = intersection.count()
    fraction = ic / sc

    if fraction < 0.9999:
        raise ValidationError(
            f"Fraction of records overlapping with reference < 99.99%"
        )

    with tempfile.NamedTemporaryFile() as ntf:
        intersection.saveas(ntf.name, compressed=True)

        with open(ntf.name, "rb") as f:
            study_data = StudyData(
                reference_genome=study_instance.submitted_data.reference_genome
            )
            study_data.data.save(
                f"{study_instance.study_id}.bed.gz", File(f), save=False
            )
            study_data.metadata = {
                "total_submitted_records": sc,
                "intersection_with_reference": ic,
                "overlapping_fraction": fraction,
            }
            study_data.save()

        study_instance.preprocessed_data = study_data
        study_instance.save(update_fields=["preprocessed_data"])


@shared_task(bind=True)
def convert_bedpe_to_bed(self, study_model, instance_id):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("preprocessed_data").get(
        id=instance_id
    )
    file_in = study_instance.preprocessed_data.data.path

    # Define output header for BED
    header = AssociationRecord.expected_order

    with tempfile.NamedTemporaryFile() as tdf:
        output = tdf.name

        with pysam.BGZFile(file_in, "r") as fin, pysam.BGZFile(output, "w") as out:

            # Write header line
            out.write(("\t".join(header) + "\n").encode())

            for raw_line in fin:
                line = raw_line.decode().rstrip("\n")
                if line.startswith("#") or not line.strip():
                    continue

                fields = line.split("\t")

                # #chrom1, start1, end1, chrom2, start2, end2, name, score, strand1, strand2, es, p-value
                chrom1, start1, end1, chrom2, start2, end2 = fields[:6]
                score, strand1, strand2 = fields[7:10]
                es, p_value = fields[10:12]

                identifier = f"{chrom1}:{start1}-{end1}--{chrom2}:{start2}-{end2}"

                left_line = (
                    "\t".join(
                        [chrom1, start1, end1, identifier, score, strand1, es, p_value]
                    )
                    + "\n"
                )

                right_line = (
                    "\t".join(
                        [chrom2, start2, end2, identifier, score, strand2, es, p_value]
                    )
                    + "\n"
                )

                out.write(left_line.encode())
                out.write(right_line.encode())

        with open(output, "rb") as f:
            study_instance.preprocessed_data.data.save(
                f"{study_instance.study_id}.bed.gz", File(f)
            )


@shared_task(bind=True)
def adjust_pvalue_task(self, study_model, instance_id, method: str = "fdr_by"):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("preprocessed_data").get(
        id=instance_id
    )
    data_path = study_instance.preprocessed_data.data.path

    # Pass 1: collect p-values only to avoid memory usage peak
    pvalues = []
    for chunk in pd.read_table(data_path, chunksize=10000):
        pvalues.extend(chunk["p-value"].values)

    # Compute adjusted p-values
    _, fdrs, _, _ = multipletests(pvalues, method=method)

    # Pass 2: stream and write output
    with tempfile.TemporaryDirectory() as td:
        outname_raw = os.path.join(td, "out.bed")
        outname_compressed = os.path.join(td, "out.bed.gz")

        eps = np.nextafter(0, 1)

        for i, chunk in enumerate(pd.read_table(data_path, chunksize=10000)):
            chunk["-log10(p-value)"] = chunk["p-value"].map(
                lambda p: abs(-np.log10(p + eps))
            )
            chunk["FDR"] = fdrs[i : i + len(chunk)]

            chunk["-log10(FDR)"] = chunk["FDR"].map(lambda p: abs(-np.log10(p + eps)))
            chunk["score"] = chunk["-log10(FDR)"] * chunk["es"].abs()

            chunk.to_csv(outname_raw, mode="a", index=False, sep="\t", header=(i == 0))

        BedTool(outname_raw).saveas(outname_compressed, compressed=True)

        # Save instance
        with open(outname_compressed, "rb") as f:
            study_instance.preprocessed_data.data.save(
                f"{study_instance.study_id}.bed.gz", File(f)
            )


@shared_task(bind=True)
def compute_ci_task(self, study_model, instance_id, alpha: float = 0.05):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("preprocessed_data").get(
        id=instance_id
    )
    data_path = study_instance.preprocessed_data.data.path

    z = norm.ppf(1 - alpha / 2)
    with tempfile.TemporaryDirectory() as td:
        outname_raw = os.path.join(td, "out.bed")
        outname_compressed = os.path.join(td, "out.bed.gz")

        for i, chunk in enumerate(pd.read_table(data_path, chunksize=10000)):
            chunk["ci"] = chunk["se"] * z
            chunk["score"] = chunk["me"]
            chunk.to_csv(outname_raw, mode="a", index=False, sep="\t", header=(i == 0))

        BedTool(outname_raw).saveas(outname_compressed, compressed=True)

        # Save instance
        with open(outname_compressed, "rb") as f:
            study_instance.preprocessed_data.data.save(
                f"{study_instance.study_id}.bed.gz", File(f)
            )


@shared_task(bind=True)
def move_from_study_to_data_task(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    study_class = apps.get_model("studies", study_model)
    study_instance = study_class.objects.select_related("preprocessed_data").get(
        id=instance_id
    )

    data_class = apps.get_model("datasets", data_model)
    data_instance, _ = data_class.objects.get_or_create(
        study=study_instance,
        reference_genome=study_instance.submitted_data.reference_genome,
        data_type=DataTypes.bed,
        liftover=False,
    )

    with study_instance.preprocessed_data.data.open("rb") as f:
        data_instance.data.save(
            f"{study_instance.study_id}.{study_instance.submitted_data.reference_genome.name}.bed.gz",
            File(f),
            save=True,
        )


@shared_task(bind=True)
def liftover_task(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    initial_data_instance = data_class.objects.select_related(
        "study", "reference_genome"
    ).get(study__id=instance_id, liftover=False)

    chain_files = ChainFile.objects.filter(
        source_genome=initial_data_instance.reference_genome
    )

    for chain_file in chain_files:
        with transaction.atomic():
            new_data_instance, _ = data_class.objects.get_or_create(
                study=initial_data_instance.study,
                reference_genome=chain_file.target_genome,
                defaults={"liftover": True},
                data_type=DataTypes.bed,
            )

            file_in = initial_data_instance.data.path
            with tempfile.NamedTemporaryFile() as file_out:
                lift_over(
                    initial_data_instance.data.path,
                    file_out.name,
                    chain_file.file.path,
                    DataTypes.bed,
                )

                with open(file_out.name, "rb") as f:
                    new_data_instance.data.save(
                        f"{initial_data_instance.study.study_id}.{chain_file.target_genome.name}.bed.gz",
                        File(f),
                        save=False,
                    )
                report = lift_over_metrics(file_in, file_out.name)

            new_data_instance.data_conversion_metrics = report
            new_data_instance.liftover = True
            new_data_instance.save()


@shared_task(bind=True)
def sort_and_index_task(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    data_instances = data_class.objects.filter(study__id=instance_id)

    for instance in data_instances:
        name = os.path.basename(instance.data.path)
        ref = instance.reference_genome.name

        with tempfile.NamedTemporaryFile(prefix=name) as ntf:
            shutil.copy(instance.data.path, ntf.name)
            sorted_gzp_path, index_path = sort_index_bgzip(ntf.name, DataTypes.bed)

            with open(sorted_gzp_path, "rb") as f, open(index_path, "rb") as i:
                instance.data.save(
                    f"{instance.study.study_id}.{ref}.sorted.bed.gz",
                    File(f),
                    save=False,
                )
                instance.data_index.save(
                    f"{instance.study.study_id}.{ref}.sorted.bed.gz.tbi",
                    File(i),
                    save=False,
                )

            instance.save(update_fields=["data", "data_index"])


@shared_task(bind=True)
def annotate_file_task(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    data_instances = data_class.objects.filter(study__id=instance_id)

    for data_instance in data_instances:
        gff = BedTool(data_instance.reference_genome.annotations_file.path)
        bed = BedTool(data_instance.data.path)

        bed_headers = pd.read_table(
            data_instance.data.path, nrows=1, compression="gzip"
        ).columns.tolist()
        gff_headers = [
            "seqname",
            "source",
            "feature",
            "feature_start",
            "feature_end",
            "feature_score",
            "feature_strand",
            "frame",
            "attributes",
        ]

        # both gff and bed/bedpe files have to be stored
        # it's critical from the optimization perspective
        annotations = gff.intersect(bed, wo=True, sorted=True).to_dataframe()
        annotations.columns = [*gff_headers, *bed_headers, "ovp"]
        annotations[["seqname", "#chrom"]] = annotations[["seqname", "#chrom"]].astype(
            str
        )

        with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp_file:
            tmp_name = tmp_file.name
            annotations.to_parquet(tmp_name, engine="pyarrow", index=None)

            with open(tmp_name, "rb") as f:
                data_instance.annotations.save(
                    f"{data_instance.study.study_id}.annotations.{data_instance.reference_genome.name}.parquet",
                    File(f),
                    save=False,
                )

        data_instance.annotations_metrics = (
            annotations["feature"].value_counts().to_dict()
        )
        data_instance.save(update_fields=["annotations", "annotations_metrics"])


@shared_task(bind=True)
def generate_association_study_plots(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    data_instances = data_class.objects.filter(study__id=instance_id)

    for data_instance in data_instances:
        mh_plot = manhattan(data_instance.data.path)
        qq_plot = qq(data_instance.data.path)
        bar_plot = bar(data_instance.annotations_metrics)

        data_instance.plots = {"mh": mh_plot, "qq": qq_plot, "an": bar_plot}
        data_instance.save(update_fields=["plots"])


@shared_task(bind=True)
def generate_interaction_study_plots(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    data_instances = data_class.objects.filter(study__id=instance_id)

    for data_instance in data_instances:
        mh_plot = manhattan(data_instance.data.path)
        qq_plot = qq(data_instance.data.path)
        bar_plot = bar(data_instance.annotations_metrics)

        data_instance.plots = {"mh": mh_plot, "qq": qq_plot, "an": bar_plot}
        data_instance.save(update_fields=["plots"])


@shared_task(bind=True)
def generate_profiling_study_plots(self, study_model, instance_id, data_model):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.RUNNING
    )

    data_class = apps.get_model("datasets", data_model)
    data_instances = data_class.objects.filter(study__id=instance_id)

    for data_instance in data_instances:
        mh_plot = violin(data_instance.data.path, value_col="me")
        data_instance.plots = {"vl": mh_plot}
        data_instance.save(update_fields=["plots"])


@shared_task(bind=True)
def integration_passed(self, study_model, instance_id):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.PASSED
    )


@shared_task(bind=True)
def integration_failed(self, study_model, instance_id):
    update_integration_status(
        study_model, instance_id, self.request.id, IntegrationStatus.FAILED
    )


@shared_task
def notify_reviewer_task(user_id):
    user = User.objects.get(id=user_id)
    print(f"Sending email to assigned reviewer: {user.email}")
