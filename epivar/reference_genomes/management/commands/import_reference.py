import os
import tempfile
from pathlib import Path
import shutil

import pandas as pd
from django.core.files import File
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from pybedtools import BedTool

from reference_genomes.models import Assembly, ReferenceGenome
from ._private import download_file


ref_data = [
    {
        "name": Assembly.HG19,
        "version": "Ensembl GRCh37 Release 114",
        "annotations": "https://ftp.ensembl.org/pub/grch37/current/gff3/homo_sapiens/Homo_sapiens.GRCh37.87.gff3.gz",
        "chrom_size_file": "https://hgdownload.cse.ucsc.edu/goldenpath/hg19/bigZips/hg19.chrom.sizes",
    },
    {
        "name": Assembly.HG38,
        "version": "Ensembl GRCh38 Release 114",
        "annotations": "https://ftp.ensembl.org/pub/release-114/gff3/homo_sapiens/Homo_sapiens.GRCh38.114.gff3.gz",
        "chrom_size_file": "https://hgdownload.soe.ucsc.edu/goldenpath/hg38/bigZips/hg38.chrom.sizes",
    },
    {
        "name": Assembly.T2T,
        "version": "CHM13v2.0",
        "annotations": "https://ftp.ensembl.org/pub/rapid-release/species/Homo_sapiens/GCA_009914755.4/ensembl/geneset/2022_07/Homo_sapiens-GCA_009914755.4-2022_07-genes.gff3.gz",
        "chrom_size_file": "https://hgdownload.soe.ucsc.edu/goldenPath/hs1/bigZips/hs1.chrom.sizes.txt",
    },
]


class Command(BaseCommand):
    help = "Import genome data (annotations + chrom.sizes) using pybedtools.tabix"

    def handle(self, *args, **options):
        for record in ref_data:
            try:
                instance = ReferenceGenome.objects.get(name=record["name"])
                self.stdout.write(f"{instance.name} already exists, skipping ...")
                continue
            except ObjectDoesNotExist:
                instance = ReferenceGenome(
                    name=record["name"], version=record["version"]
                )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)

                # -----------------------
                # 1. Download annotations
                # -----------------------
                self.stdout.write("Downloading annotations file...")
                annotation_path = download_file(record["annotations"], tmpdir)

                self.stdout.write("Sorting + tabix GFF with pybedtools...")
                gff_bt = BedTool(str(annotation_path)).sort()
                gff_tabix = gff_bt.tabix(force=True, is_sorted=True)

                ann_gz = tmpdir / "annotations.gff3.gz"
                ann_tbi = tmpdir / "annotations.gff3.gz.tbi"
                shutil.move(gff_tabix.fn, ann_gz)
                shutil.move(gff_tabix.fn + ".tbi", ann_tbi)

                with open(ann_gz, "rb") as s, open(ann_tbi, "rb") as i:
                    instance.annotations_file.save(ann_gz.name, File(s), save=False)
                    instance.annotations_file_index.save(ann_tbi.name, File(i), save=False)

                # -----------------------
                # 2. Download chrom sizes
                # -----------------------
                self.stdout.write("Downloading chrom.sizes file...")
                chrom_size_path = download_file(record["chrom_size_file"], tmpdir)

                chrom_df = pd.read_table(chrom_size_path, header=None)
                chrom_df.columns = ["#chrom", "end"]

                # Normalize names: strip chr, fix M→MT
                chrom_df["#chrom"] = chrom_df["#chrom"].str.replace("^chr", "", regex=True)
                chrom_df["#chrom"] = chrom_df["#chrom"].str.replace("M$", "MT", regex=True)

                # Save normalized chrom.sizes (2-column file)
                norm_chrom_sizes = tmpdir / "chrom_sizes.txt"
                chrom_df.to_csv(norm_chrom_sizes, sep="\t", header=False, index=False)

                with open(norm_chrom_sizes, "rb") as c:
                    instance.chrom_size_file.save(norm_chrom_sizes.name, File(c), save=False)

                # -----------------------
                # Convert chrom.sizes → BED
                # -----------------------
                chrom_df["start"] = 0
                chrom_bed = chrom_df[["#chrom", "start", "end"]]

                if chrom_bed.empty:
                    raise ValueError("Converted chrom.sizes BED is empty!")

                bed_tmp = tmpdir / "chrom_sizes.bed"

                # Write with BED header
                chrom_bed.to_csv(
                    bed_tmp,
                    sep="\t",
                    header=["#chrom", "start", "end"],
                    index=False,
                )

                self.stdout.write("Sorting + tabix BED with pybedtools...")
                bed_bt = BedTool(str(bed_tmp)).sort(header=True)
                bed_tabix = bed_bt.tabix(force=True, is_sorted=True)

                bed_gz = tmpdir / "chrom_sizes.bed.gz"
                bed_tbi = tmpdir / "chrom_sizes.bed.gz.tbi"
                shutil.move(bed_tabix.fn, bed_gz)
                shutil.move(bed_tabix.fn + ".tbi", bed_tbi)

                with open(bed_gz, "rb") as s, open(bed_tbi, "rb") as i:
                    instance.chrom_size_file_bed.save(bed_gz.name, File(s), save=False)
                    instance.chrom_size_file_bed_index.save(bed_tbi.name, File(i), save=False)

                # -----------------------
                # Save final instance
                # -----------------------
                instance.save()
                self.stdout.write(self.style.SUCCESS(f"Imported {instance.name}"))
