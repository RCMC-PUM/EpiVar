import os
import re
import shutil
import tempfile
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


features_data = [
    {
        "name": "SCREEN - Search Candidate cis-Regulatory Elements by ENCODE",
        "description": "SCREEN - Search Candidate cis-Regulatory Elements by ENCODE",
        "reference_genome": "hg38",  # must match ReferenceGenome.name
        "url": "https://downloads.wenglab.org/Registry-V4/GRCh38-cCREs.bed",
    },
]


class Command(BaseCommand):
    help = "Prepare and import SCREEN genomic features (split heterogeneous BED into homogeneous files by last column, assign to collection)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing GenomicFeature records with the same name",
        )

    def handle(self, *args, **options):
        force = options["force"]

        for record in features_data:
            self.stdout.write(f"Processing collection: {record['name']}")

            try:
                reference_genome = ReferenceGenome.objects.get(
                    name=record["reference_genome"]
                )
            except ObjectDoesNotExist:
                raise CommandError(
                    f"ReferenceGenome {record['reference_genome']} not found. Import genomes first."
                )

            # ----------------------------
            # 1. Create/get collection
            # ----------------------------
            collection, _ = GenomicFeatureCollection.objects.get_or_create(
                name=record["name"],
                defaults={
                    "description": record["description"],
                    "reference_genome": reference_genome,
                    "reference": "SCREEN: Search Candidate cis-Regulatory Elements by ENCODE v3",
                    "reference_url": "https://screen.encodeproject.org/",
                },
            )

            # ----------------------------
            # 2. Download BED
            # ----------------------------
            file_path = download_file(record["url"])
            file_path = str(file_path)

            # ----------------------------
            # 3. Split into per-label sets by last column
            # ----------------------------
            label_records = defaultdict(list)
            with open(file_path, "r") as infile:
                for line in infile:
                    if line.startswith("#") or line.lower().startswith("chrom") or line.strip() == "":
                        continue
                    parts = line.rstrip("\n").split("\t")
                    chrom, start, end = parts[0], parts[1], parts[2]
                    label = parts[-1]

                    if chrom.startswith("chr"):
                        chrom = chrom[3:]

                    label_records[label].append("\t".join([chrom, start, end, label]))

            # ----------------------------
            # 4. For each label, create/update GenomicFeature
            # ----------------------------
            for label, lines in label_records.items():
                feature_name = f"{record['name']} - {label}"

                try:
                    feature = GenomicFeature.objects.get(name=feature_name)
                    if not force:
                        self.stdout.write(f"{feature.name} already exists, skipping ...")
                        continue
                    else:
                        self.stdout.write(f"{feature.name} exists, overwriting ...")
                except ObjectDoesNotExist:
                    feature = GenomicFeature(
                        name=feature_name,
                        description=f"{record['description']} ({label})",
                        reference_genome=reference_genome,
                        collection=collection,
                    )

                with tempfile.TemporaryDirectory() as td:
                    safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", label)
                    bed_file = os.path.join(td, f"{record['name']}_{safe_label}.bed")

                    with open(bed_file, "w") as out:
                        out.write("#chrom\tstart\tend\tname\n")
                        out.write("\n".join(lines) + "\n")

                    # Validate vs chrom.sizes
                    features_bt = BedTool(bed_file)
                    chromsizes_bt = BedTool(reference_genome.chrom_size_file_bed.path)
                    intersection = features_bt.intersect(chromsizes_bt, u=True)
                    if features_bt.count() < intersection.count():
                        raise ValidationError(
                            f"File {bed_file} does not match {reference_genome.name}"
                        )

                    # Sort + tabix
                    self.stdout.write(f"Sorting + tabix {feature_name} ...")
                    sorted_bt = BedTool(bed_file).sort(header=True)
                    tabix_bt = sorted_bt.tabix(force=True, is_sorted=True)

                    bed_gz = os.path.join(td, f"{record['name']}_{safe_label}.bed.gz")
                    bed_tbi = bed_gz + ".tbi"

                    shutil.move(tabix_bt.fn, bed_gz)
                    shutil.move(tabix_bt.fn + ".tbi", bed_tbi)

                    with open(bed_gz, "rb") as s, open(bed_tbi, "rb") as i:
                        feature.file.save(os.path.basename(bed_gz), File(s), save=False)
                        feature.file_index.save(os.path.basename(bed_tbi), File(i), save=False)

                feature.reference = "SCREEN: Search Candidate cis-Regulatory Elements by ENCODE v3"
                feature.reference_url = "https://screen.encodeproject.org/"
                feature.collection = collection

                feature.save()
                self.stdout.write(self.style.SUCCESS(f"Imported {feature.name} into {collection.name}"))
