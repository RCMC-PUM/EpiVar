import os
import re
import shutil
import tempfile
from collections import defaultdict

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from pybedtools import BedTool

from reference_genomes.models import (
    GenomicFeature,
    GenomicFeatureCollection,
    ReferenceGenome,
)
from ._private import _download_file, _validate_against_chrom_sizes


# Each record can define how to interpret the "BED-like" file
features_data = [
    {
        "name": "SCREEN V3",
        "description": "SCREEN - Search Candidate cis-Regulatory Elements by ENCODE (V3)",
        "reference_genome": "hg38",  # must match ReferenceGenome.name
        "url": "https://downloads.wenglab.org/Registry-V4/GRCh38-cCREs.bed",
        "label_column_index": -1,
        "label_mapper": {"PLS": "Promoter-like",
                         "pELS": "Proximal enhancer-like",
                         "dELS": "Distal enhancer-like",
                         "CA-CTCF": "Chromatin accessible with CTCF",
                         "CA-H3K4me3": "Chromatin accessible with H3K4me3",
                         "CA-TF": "Chromatin accessible with TF",
                         "CA": "Chromatin accessible only",
                         "TF": "TF only"}
    },
]


class Command(BaseCommand):
    help = (
        "Prepare and import genomic features from BED-like files. "
        "Splits heterogeneous files into homogeneous per-label files and assigns them to a collection."
    )

    # ------------------------------------------------------------------
    # Helpers: model lookups / collection
    # ------------------------------------------------------------------
    @staticmethod
    def _get_reference_genome(name: str) -> ReferenceGenome:
        try:
            return ReferenceGenome.objects.get(name=name)
        except ObjectDoesNotExist:
            raise CommandError(
                f"ReferenceGenome {name} not found. Import genomes first."
            )

    @staticmethod
    def _get_or_create_collection(
        record: dict,
        reference_genome: ReferenceGenome,
    ) -> GenomicFeatureCollection:
        collection, _ = GenomicFeatureCollection.objects.get_or_create(
            name=record["name"],
            defaults={
                "description": record["description"],
                "reference_genome": reference_genome,
                "reference": "SCREEN: Search Candidate cis-Regulatory Elements by ENCODE v4",
                "reference_url": "https://screen.encodeproject.org/",
            },
        )
        return collection

    # ------------------------------------------------------------------
    # Helpers: I/O and parsing
    # ------------------------------------------------------------------

    def _download_source_file(self, url: str, tmpdir) -> str:
        self.stdout.write(f"Downloading source file from {url} ...")
        file_path = _download_file(url, tmpdir)
        return str(file_path)

    @staticmethod
    def _split_bed_like_by_label(file_path: str, record: dict) -> dict:
        """
        Read a BED-like file and split it into groups by the label column.
        Config is taken from the record dict:
        """
        label_records = defaultdict(list)
        with open(file_path, "r") as infile:
            for line in infile:
                line = line.rstrip("\n")

                if not line:
                    continue

                if line.startswith("#") or line.startswith("track"):
                    continue

                parts = line.split("\t")

                try:
                    chrom = parts[0]
                    if not str(chrom).startswith("chr"):
                        chrom = f"chr{chrom}"

                    start = parts[1]
                    end = parts[2]
                    label = parts[record["label_column_index"]]
                except IndexError:
                    continue

                # Output as standard 4-column BED: chrom, start, end, label
                if record["label_mapper"]:
                    label = record["label_mapper"][label]

                label_records[label].append(
                    "\t".join([chrom, start, end, label])
                )

        return label_records

    # ------------------------------------------------------------------
    # Helpers: per-label import
    # ------------------------------------------------------------------
    def _import_label_groups(
        self,
        label_records: dict,
        record: dict,
        reference_genome: ReferenceGenome,
        collection: GenomicFeatureCollection,
        force: bool,
        tmpdir: str
    ) -> None:
        for label, lines in label_records.items():
            feature_name = f"{record['name']} - {label}"
            feature = self._get_or_create_feature(
                feature_name, label, record, reference_genome, collection, force
            )

            if feature is None:
                # skipped because exists and not --force
                continue

            bed_file = self._write_bed_file(record["name"], label, lines, tmpdir)
            _validate_against_chrom_sizes(
                bed_file, reference_genome.chrom_size_file_bed.path
            )
            bed_gz, bed_tbi = self._sort_and_tabix(
                bed_file, record["name"], label, tmpdir
            )
            self._attach_feature_files(feature, bed_gz, bed_tbi)

            feature.reference = (
                "SCREEN: Search Candidate cis-Regulatory Elements by ENCODE v4"
            )
            feature.reference_url = "https://screen.encodeproject.org/"
            feature.collection = collection
            feature.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {feature.name} into {collection.name}"
                )
            )

    def _get_or_create_feature(
        self,
        feature_name: str,
        label: str,
        record: dict,
        reference_genome: ReferenceGenome,
        collection: GenomicFeatureCollection,
        force: bool,
    ) -> GenomicFeature | None:
        try:
            feature = GenomicFeature.objects.get(name=feature_name)
            if not force:
                self.stdout.write(f"{feature.name} already exists, skipping ...")
                return None
            else:
                self.stdout.write(f"{feature.name} exists, overwriting ...")
                return feature

        except ObjectDoesNotExist:
            return GenomicFeature(
                name=feature_name,
                description=f"{record['name']} - {label}",
                reference_genome=reference_genome,
                collection=collection,
            )

    @staticmethod
    def _write_bed_file(
        base_name: str,
        label: str,
        lines: list[str],
        tmpdir: str,
    ) -> str:
        safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
        bed_file = os.path.join(tmpdir, f"{base_name}_{safe_label}.bed")

        with open(bed_file, "w") as out:
            out.write("#chrom\tstart\tend\tname\n")
            out.write("\n".join(lines) + "\n")

        return bed_file

    def _sort_and_tabix(
        self,
        bed_file: str,
        base_name: str,
        label: str,
        tmpdir: str,
    ) -> tuple[str, str]:
        self.stdout.write(f"Sorting + tabix {base_name} - {label} ...")

        sorted_bt = BedTool(bed_file).sort(header=True)
        tabix_bt = sorted_bt.tabix(force=True, is_sorted=True)

        safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
        bed_gz = os.path.join(tmpdir, f"{base_name}_{safe_label}.bed.gz")
        bed_tbi = bed_gz + ".tbi"

        shutil.move(tabix_bt.fn, bed_gz)
        shutil.move(tabix_bt.fn + ".tbi", bed_tbi)

        return bed_gz, bed_tbi

    @staticmethod
    def _attach_feature_files(
        feature: GenomicFeature,
        bed_gz: str,
        bed_tbi: str,
    ) -> None:
        with open(bed_gz, "rb") as s, open(bed_tbi, "rb") as i:
            feature.file.save(os.path.basename(bed_gz), File(s), save=False)
            feature.file_index.save(os.path.basename(bed_tbi), File(i), save=False)

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing GenomicFeature records with the same name",
        )

    def handle(self, *args, **options):
        force = options["force"]

        for record in features_data:
            with tempfile.TemporaryDirectory() as tmpdir:
                self.stdout.write(f"Processing collection: {record['name']}")

                reference_genome = self._get_reference_genome(record["reference_genome"])
                collection = self._get_or_create_collection(record, reference_genome)

                source_path = self._download_source_file(record["url"], tmpdir)
                label_records = self._split_bed_like_by_label(source_path, record)

                if not label_records:
                    raise CommandError(
                        f"No usable records found in file for collection {record['name']}"
                    )

                self._import_label_groups(
                    label_records, record, reference_genome, collection, force, tmpdir
                )
