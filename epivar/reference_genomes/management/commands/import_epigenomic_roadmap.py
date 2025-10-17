import os
import re
import shutil
import tempfile
import gzip
from collections import defaultdict

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from pybedtools import BedTool

from reference_genomes.models import (
    GenomicFeature,
    GenomicFeatureCollection,
    ReferenceGenome,
)
from ._private import download_file


# Add this near your STATE_MAP
STATE_MAP_15 = {
    "1": "TssA",
    "2": "TssAFlnk",
    "3": "TxFlnk",
    "4": "Tx",
    "5": "TxWk",
    "6": "EnhG",
    "7": "Enh",
    "8": "ZNF/Rpts",
    "9": "Het",
    "10": "TssBiv",
    "11": "BivFlnk",
    "12": "EnhBiv",
    "13": "ReprPC",
    "14": "ReprPCWk",
    "15": "Quies",
}

STATE_MAP_18 = {
    "1": "TssA",
    "2": "TssAFlnk",
    "3": "TxFlnk",
    "4": "Tx",
    "5": "TxWk",
    "6": "EnhG",
    "7": "Enh",
    "8": "ZNF/Rpts",
    "9": "Het",
    "10": "TssBiv",
    "11": "BivFlnk",
    "12": "EnhBiv",
    "13": "ReprPC",
    "14": "ReprPCWk",
    "15": "Quies",
    "16": "EnhA1",
    "17": "EnhA2",
    "18": "TxEnhWk",
}

MODEL_CONFIGS = {
    "15-core": {
        "base_url": "https://egg2.wustl.edu/roadmap/data/byFileType/chromhmmSegmentations/ChmmModels/coreMarks/jointModel/final/",
        "fname_template": "{eid}_15_coreMarks_hg38lift_stateno.bed.gz",
        "state_map": STATE_MAP_15,
        "reference": "15 State Core Model",
        "reference_url": "https://egg2.wustl.edu/roadmap/web_portal/chr_state_learning.html",
    },
    "18-coreK27ac": {
        "base_url": "https://egg2.wustl.edu/roadmap/data/byFileType/chromhmmSegmentations/ChmmModels/core_K27ac/jointModel/final/",
        "fname_template": "{eid}_18_core_K27ac_hg38lift_stateno.bed.gz",
        "state_map": STATE_MAP_18,
        "reference": "18 State K27ac Model",
        "reference_url": "https://egg2.wustl.edu/roadmap/web_portal/chr_state_learning.html",
    },
}

CELL_TYPE_MAP = {
    "E017": "IMR90 fetal lung fibroblasts Cell Line",
    "E002": "ES-WA7 Cells",
    "E008": "H9 Cells",
    "E001": "ES-I3 Cells",
    "E015": "HUES6 Cells",
    "E014": "HUES48 Cells",
    "E016": "HUES64 Cells",
    "E003": "H1 Cells",
    "E024": "ES-UCSF4 Cells",
    "E020": "iPS-20b Cells",
    "E019": "iPS-18 Cells",
    "E018": "iPS-15b Cells",
    "E021": "iPS DF 6.9 Cells",
    "E022": "iPS DF 19.11 Cells",
    "E007": "H1 Derived Neuronal Progenitor Cultured Cells",
    "E009": "H9 Derived Neuronal Progenitor Cultured Cells",
    "E010": "H9 Derived Neuron Cultured Cells",
    "E013": "hESC Derived CD56+ Mesoderm Cultured Cells",
    "E012": "hESC Derived CD56+ Ectoderm Cultured Cells",
    "E011": "hESC Derived CD184+ Endoderm Cultured Cells",
    "E004": "H1 BMP4 Derived Mesendoderm Cultured Cells",
    "E005": "H1 BMP4 Derived Trophoblast Cultured Cells",
    "E006": "H1 Derived Mesenchymal Stem Cells",
    "E062": "Primary mononuclear cells from peripheral blood",
    "E034": "Primary T cells from peripheral blood",
    "E045": "Primary T cells effector/memory enriched from peripheral blood",
    "E033": "Primary T cells from cord blood",
    "E044": "Primary T regulatory cells from peripheral blood",
    "E043": "Primary T helper cells from peripheral blood",
    "E039": "Primary T helper naive cells from peripheral blood",
    "E041": "Primary T helper cells PMA-I stimulated",
    "E042": "Primary T helper 17 cells PMA-I stimulated",
    "E040": "Primary T helper memory cells from peripheral blood 1",
    "E037": "Primary T helper memory cells from peripheral blood 2",
    "E048": "Primary T CD8+ memory cells from peripheral blood",
    "E038": "Primary T helper naive cells from peripheral blood",
    "E047": "Primary T CD8+ naive cells from peripheral blood",
    "E029": "Primary monocytes from peripheral blood",
    "E031": "Primary B cells from cord blood",
    "E035": "Primary hematopoietic stem cells",
    "E051": "Primary hematopoietic stem cells G-CSF-mobilized Male",
    "E050": "Primary hematopoietic stem cells G-CSF-mobilized Female",
    "E036": "Primary hematopoietic stem cells short term culture",
    "E032": "Primary B cells from peripheral blood",
    "E046": "Primary Natural Killer cells from peripheral blood",
    "E030": "Primary neutrophils from peripheral blood",
    "E026": "Bone Marrow Derived Cultured Mesenchymal Stem Cells",
    "E049": "Mesenchymal Stem Cell Derived Chondrocyte Cultured Cells",
    "E025": "Adipose Derived Mesenchymal Stem Cell Cultured Cells",
    "E023": "Mesenchymal Stem Cell Derived Adipocyte Cultured Cells",
    "E052": "Muscle Satellite Cultured Cells",
    "E055": "Foreskin Fibroblast Primary Cells skin01",
    "E056": "Foreskin Fibroblast Primary Cells skin02",
    "E059": "Foreskin Melanocyte Primary Cells skin01",
    "E061": "Foreskin Melanocyte Primary Cells skin03",
    "E057": "Foreskin Keratinocyte Primary Cells skin02",
    "E058": "Foreskin Keratinocyte Primary Cells skin03",
    "E028": "Breast variant Human Mammary Epithelial Cells (vHMEC)",
    "E027": "Breast Myoepithelial Primary Cells",
    "E054": "Ganglion Eminence derived primary cultured neurospheres",
    "E053": "Cortex derived primary cultured neurospheres",
    "E112": "Thymus",
    "E093": "Fetal Thymus",
    "E071": "Brain Hippocampus Middle",
    "E074": "Brain Substantia Nigra",
    "E068": "Brain Anterior Caudate",
    "E069": "Brain Cingulate Gyrus",
    "E072": "Brain Inferior Temporal Lobe",
    "E067": "Brain Angular Gyrus",
    "E073": "Brain Dorsolateral Prefrontal Cortex",
    "E070": "Brain Germinal Matrix",
    "E082": "Fetal Brain Female",
    "E081": "Fetal Brain Male",
    "E063": "Adipose Nuclei",
    "E100": "Psoas Muscle",
    "E108": "Skeletal Muscle Female",
    "E107": "Skeletal Muscle Male",
    "E089": "Fetal Muscle Trunk",
    "E090": "Fetal Muscle Leg",
    "E083": "Fetal Heart",
    "E104": "Right Atrium",
    "E095": "Left Ventricle",
    "E105": "Right Ventricle",
    "E065": "Aorta",
    "E078": "Duodenum Smooth Muscle",
    "E076": "Colon Smooth Muscle",
    "E103": "Rectal Smooth Muscle",
    "E111": "Stomach Smooth Muscle",
    "E092": "Fetal Stomach",
    "E085": "Fetal Intestine Small",
    "E084": "Fetal Intestine Large",
    "E109": "Small Intestine",
    "E106": "Sigmoid Colon",
    "E075": "Colonic Mucosa",
    "E101": "Rectal Mucosa Donor 29",
    "E102": "Rectal Mucosa Donor 31",
    "E110": "Stomach Mucosa",
    "E077": "Duodenum Mucosa",
    "E079": "Esophagus",
    "E094": "Gastric",
    "E099": "Placenta Amnion",
    "E086": "Fetal Kidney",
    "E088": "Fetal Lung",
    "E097": "Ovary",
    "E087": "Pancreatic Islets",
    "E080": "Fetal Adrenal Gland",
    "E091": "Placenta",
    "E066": "Liver",
    "E098": "Pancreas",
    "E096": "Lung",
    "E113": "Spleen",
    "E114": "A549 EtOH 0.02pct Lung Carcinoma Cell Line",
    "E115": "Dnd41 TCell Leukemia Cell Line",
    "E116": "GM12878 Lymphoblastoid Cells",
    "E117": "HeLa-S3 Cervical Carcinoma Cell Line",
    "E118": "HepG2 Hepatocellular Carcinoma Cell Line",
    "E119": "HMEC Mammary Epithelial Primary Cells",
    "E120": "HSMM Skeletal Muscle Myoblasts Cells",
    "E121": "HSMM cell derived Skeletal Muscle Myotubes Cells",
    "E122": "HUVEC Umbilical Vein Endothelial Primary Cells",
    "E123": "K562 Leukemia Cells",
    "E124": "Monocytes-CD14+ RO01746 Primary Cells",
    "E125": "NH-A Astrocytes Primary Cells",
    "E126": "NHDF-Ad Adult Dermal Fibroblast Primary Cells",
    "E127": "NHEK-Epidermal Keratinocyte Primary Cells",
    "E128": "NHLF Lung Fibroblast Primary Cells",
    "E129": "Osteoblast Primary Cells",
}

BASE_URL = (
    "https://egg2.wustl.edu/roadmap/data/byFileType/chromhmmSegmentations/"
    "ChmmModels/coreMarks/jointModel/final/"
)


class Command(BaseCommand):
    help = "Download, normalize, and import roadmap segmentations into per-state GenomicFeatures grouped by Collection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Overwrite existing features"
        )

    def handle(self, *args, **options):
        force = options["force"]

        try:
            reference_genome = ReferenceGenome.objects.get(name="hg38")
        except ObjectDoesNotExist:
            raise CommandError("ReferenceGenome hg38 not found. Import genomes first.")

        for eid, cell_name in CELL_TYPE_MAP.items():
            for model_key, cfg in MODEL_CONFIGS.items():
                fname = cfg["fname_template"].format(eid=eid)

                url = cfg["base_url"] + fname
                self.stdout.write(f"Processing {eid} ({cell_name}) with {model_key}")

                # 1. Download
                try:
                    file_path = download_file(url)
                    file_path = str(file_path)
                except Exception as e:
                    # Skip if file is not found (e.g., 404)
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {eid} ({cell_name}) {model_key}: {e}"
                        )
                    )
                    continue

                # 2. Split into per-state records
                state_records = defaultdict(list)
                with gzip.open(file_path, "rt") as infile:
                    for line in infile:
                        if (
                            line.startswith("#")
                            or line.startswith("track")
                            or line.strip() == ""
                        ):
                            continue
                        parts = line.rstrip("\n").split("\t")
                        if parts[0].startswith("chr"):
                            parts[0] = parts[0][3:]

                        state_no = parts[3]  # just the number in stateno format
                        state_name = cfg["state_map"].get(state_no, f"State{state_no}")

                        state_records[state_name].append(
                            "\t".join([parts[0], parts[1], parts[2], state_name])
                        )

                # 3. Create/get collection
                collection_name = f"{cell_name} - {cfg['reference']}"
                collection, _ = GenomicFeatureCollection.objects.get_or_create(
                    name=collection_name,
                    defaults={
                        "description": f"Roadmap {cfg['reference']} segmentations for {cell_name}",
                        "reference_genome": reference_genome,
                        "reference": cfg["reference"],
                        "reference_url": cfg["reference_url"],
                    },
                )

                # 4. For each state, create or update GenomicFeature
                for state, lines in state_records.items():
                    feature_name = f"{cell_name} - {state}"

                    try:
                        feature = GenomicFeature.objects.get(name=feature_name)
                        if not force:
                            self.stdout.write(
                                f"{feature.name} already exists, skipping ..."
                            )
                            continue
                        else:
                            self.stdout.write(f"{feature.name} exists, overwriting ...")

                    except ObjectDoesNotExist:
                        feature = GenomicFeature(
                            name=feature_name,
                            description=f"Roadmap {cfg['reference']} {state} segmentation for {cell_name}",
                            reference_genome=reference_genome,
                            collection=collection,
                        )

                    with tempfile.TemporaryDirectory() as td:
                        safe_state = re.sub(r"[^A-Za-z0-9._-]", "_", state)
                        bed_file = os.path.join(td, f"{eid}_{safe_state}.bed")

                        with open(bed_file, "w") as out:
                            out.write("#chrom\tstart\tend\tname\n")
                            out.write("\n".join(lines) + "\n")

                        features_bt = BedTool(bed_file)
                        chromsizes_bt = BedTool(
                            reference_genome.chrom_size_file_bed.path
                        )

                        intersection = features_bt.intersect(chromsizes_bt, u=True)
                        if features_bt.count() < intersection.count():
                            raise ValidationError(
                                f"File {bed_file} does not match {reference_genome.name}"
                            )

                        self.stdout.write(f"Sorting + tabix {feature_name} ...")
                        sorted_bt = BedTool(bed_file).sort(header=True)
                        tabix_bt = sorted_bt.tabix(force=True, is_sorted=True)

                        bed_gz = os.path.join(td, f"{eid}_{safe_state}.bed.gz")
                        bed_tbi = bed_gz + ".tbi"

                        shutil.move(tabix_bt.fn, bed_gz)
                        shutil.move(tabix_bt.fn + ".tbi", bed_tbi)

                        with open(bed_gz, "rb") as s, open(bed_tbi, "rb") as i:
                            feature.file.save(
                                os.path.basename(bed_gz), File(s), save=False
                            )
                            feature.file_index.save(
                                os.path.basename(bed_tbi), File(i), save=False
                            )

                    feature.reference = cfg["reference"]
                    feature.reference_url = cfg["reference_url"]
                    feature.collection = collection
                    feature.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Imported {feature.name} into {collection.name}"
                        )
                    )
