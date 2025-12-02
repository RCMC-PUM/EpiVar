import os
import shutil
import tempfile

import pandas as pd
from django.core.files import File
from django.core.management.base import BaseCommand
from pybedtools import BedTool

from reference_genomes.models import Assembly, ReferenceGenome
from ._private import _download_file


ref_data = [
    {
        "name": Assembly.HG19,
        "version": "GRCh37",
        "annotations": "https://hgdownload.cse.ucsc.edu/goldenpath/hg19/bigZips/genes/hg19.ncbiRefSeq.gtf.gz",
        "chrom_size_file": "https://hgdownload.cse.ucsc.edu/goldenpath/hg19/bigZips/hg19.chrom.sizes",
    },
    {
        "name": Assembly.HG38,
        "version": "GRCh38",
        "annotations": "https://hgdownload.soe.ucsc.edu/goldenpath/hg38/bigZips/genes/hg38.ncbiRefSeq.gtf.gz",
        "chrom_size_file": "https://hgdownload.soe.ucsc.edu/goldenpath/hg38/bigZips/hg38.chrom.sizes",
    },
    {
        "name": Assembly.T2T,
        "version": "CHM13v2.0",
        "annotations": "https://hgdownload.soe.ucsc.edu/goldenPath/hs1/bigZips/genes/hs1.ncbiRefSeq.gtf.gz",
        "chrom_size_file": "https://hgdownload.soe.ucsc.edu/goldenPath/hs1/bigZips/hs1.chrom.sizes.txt",
    },
]


class Command(BaseCommand):
    help = "Import genome data for hg19, hg38 and T2T reference assemblies from UCSC FTP"

    # ----------------------------
    # Private helpers
    # ----------------------------
    @staticmethod
    def _reference_genome_exists(name) -> bool:
        """Check if ReferenceGenome with given name already exists."""
        return ReferenceGenome.objects.filter(name=name).exists()

    def _prepare_annotations(self, annotations_url: str, tmpdir: str) -> tuple[str, str]:
        """
        Download annotations, sort with pybedtools, tabix index, and move
        to deterministic filenames. Returns (gz_path, tbi_path).
        """
        self.stdout.write("Downloading annotations file...")
        annotation_path = _download_file(annotations_url, tmpdir)

        self.stdout.write("Sorting + tabix GTF with pybedtools...")
        bt = BedTool(annotation_path).sort(header=True)
        tabixed = bt.tabix(force=True, is_sorted=True)

        ann_gz = os.path.join(tmpdir, "annotations.gtf.gz")
        ann_tbi = ann_gz + ".tbi"

        shutil.move(tabixed.fn, ann_gz)
        shutil.move(tabixed.fn + ".tbi", ann_tbi)

        return ann_gz, ann_tbi

    def _prepare_chrom_sizes(
            self,
            chrom_size_url: str,
            tmpdir: str,
    ) -> tuple[str, pd.DataFrame]:
        """
        Download chrom.sizes, normalize to a 2-column tab-delimited file,
        and return the normalized path and the DataFrame.
        """
        self.stdout.write("Downloading chrom.sizes file...")
        chrom_size_path = str(_download_file(chrom_size_url, tmpdir))

        chrom_df = pd.read_table(
            chrom_size_path,
            header=None,
            names=["#chrom", "end"],
        )

        norm_chrom_sizes = os.path.join(tmpdir, "chrom_sizes.txt")
        chrom_df.to_csv(norm_chrom_sizes, sep="\t", header=False, index=False)

        return norm_chrom_sizes, chrom_df

    def _chrom_sizes_to_bed_and_tabix(
            self,
            chrom_df: pd.DataFrame,
            tmpdir: str,
    ) -> tuple[str, str]:
        """
        Convert chrom.sizes DataFrame to BED, sort + tabix, return (bed_gz, bed_tbi).
        """
        chrom_df["start"] = 0
        chrom_bed = chrom_df[["#chrom", "start", "end"]]

        if chrom_bed.empty:
            raise ValueError("Converted chrom.sizes BED is empty!")

        bed_tmp = os.path.join(tmpdir, "chrom_sizes.bed")
        chrom_bed.to_csv(
            bed_tmp,
            sep="\t",
            header=["#chrom", "start", "end"],
            index=False,
        )

        self.stdout.write("Sorting + tabix BED with pybedtools...")
        bed_bt = BedTool(bed_tmp).sort(header=True)
        bed_tabix = bed_bt.tabix(force=True, is_sorted=True)

        bed_gz = os.path.join(tmpdir, "chrom_sizes.bed.gz")
        bed_tbi = bed_gz + ".tbi"

        shutil.move(bed_tabix.fn, bed_gz)
        shutil.move(bed_tabix.fn + ".tbi", bed_tbi)

        return bed_gz, bed_tbi

    # ----------------------------
    # Attach files to instance
    # ----------------------------
    def _attach_annotations(
            self,
            instance: ReferenceGenome,
            ann_gz: str,
            ann_tbi: str,
    ) -> None:
        self._attach_file(instance, "annotations_file", ann_gz)
        self._attach_file(instance, "annotations_file_index", ann_tbi)

    def _attach_chrom_sizes(
            self,
            instance: ReferenceGenome,
            chrom_sizes_txt: str,
    ) -> None:
        self._attach_file(instance, "chrom_size_file", chrom_sizes_txt)

    def _attach_file(self, instance: ReferenceGenome, field_name: str, path: str) -> None:
        """Utility to attach a file on disk to a FileField without saving the instance."""
        field = getattr(instance, field_name)
        with open(path, "rb") as fh:
            field.save(os.path.basename(path), File(fh), save=False)

    def _attach_chrom_bed(
            self,
            instance: ReferenceGenome,
            bed_gz: str,
            bed_tbi: str,
    ) -> None:
        self._attach_file(instance, "chrom_size_file_bed", bed_gz)
        self._attach_file(instance, "chrom_size_file_bed_index", bed_tbi)

    def handle(self, *args, **options):
        for record in ref_data:
            if self._reference_genome_exists(record["name"]):
                self.stdout.write(f"{record['name']} already exists, skipping ...")
                continue

            instance = ReferenceGenome(
                name=record["name"],
                version=record["version"],
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                # 1) Annotations: download + sort + tabix
                ann_gz, ann_tbi = self._prepare_annotations(
                    annotations_url=record["annotations"],
                    tmpdir=tmpdir,
                )
                self._attach_annotations(instance, ann_gz, ann_tbi)

                # 2) chrom.sizes: download + normalize
                chrom_sizes_txt, chrom_df = self._prepare_chrom_sizes(
                    chrom_size_url=record["chrom_size_file"],
                    tmpdir=tmpdir,
                )
                self._attach_chrom_sizes(instance, chrom_sizes_txt)

                # 3) chrom.sizes → BED + tabix
                bed_gz, bed_tbi = self._chrom_sizes_to_bed_and_tabix(
                    chrom_df=chrom_df,
                    tmpdir=tmpdir,
                )
                self._attach_chrom_bed(instance, bed_gz, bed_tbi)

                # 4) Save final instance
                instance.save()
                self.stdout.write(self.style.SUCCESS(f"Imported {instance.name}"))
