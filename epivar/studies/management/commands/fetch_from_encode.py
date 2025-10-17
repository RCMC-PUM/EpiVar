import requests
import pandas as pd
import tempfile
from django.core.management.base import BaseCommand
from django.db import transaction

from studies.models import ProfilingStudy, Biosample, Platform, Sample

# -------------------
# ENCODE API defaults
# -------------------
BASE = "https://www.encodeproject.org/search/"

PARAMS = {
    "type": "Dataset",
    "status": "released",
    "perturbed": "false",
    "assay_title": ["TF ChIP-seq", "Histone ChIP-seq", "DNase-seq", "ATAC-seq"],
    "replicates.library.biosample.donor.organism.scientific_name": "Homo sapiens",
    "assembly": "GRCh38",
    "files.file_type": "bed narrowPeak",
    "replication_type": ["isogenic", "anisogenic"],
    "limit": "25",
    "format": "json",
    "frame": "embedded",
}

HEADERS = {"Accept": "application/json"}


class Command(BaseCommand):
    help = "Fetch datasets from ENCODE and create ProfilingStudy objects"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Fetching from ENCODE..."))
        data = self._fetch_encode_data()
        rows = self._parse_encode_data(data)
        df = self._filter_dataframe(rows)

        self.stdout.write(
            f"Fetched {len(df)} valid files from {df['study_id'].nunique()} experiments"
        )

        for _, row in df.iterrows():
            try:
                self._create_profiling_study(row)
                self.stdout.write(self.style.SUCCESS(f"Imported {row['study_id']}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Skipping {row['study_id']} - {e}"))

        self.stdout.write(self.style.SUCCESS("Done importing ENCODE ProfilingStudies."))

    # -------------------
    # _private functions
    # -------------------

    def _fetch_encode_data(self):
        r = requests.get(BASE, params=PARAMS, headers=HEADERS)
        r.raise_for_status()
        return r.json()

    def _parse_encode_data(self, data):
        rows = []
        for exp in data.get("@graph", []):
            exp_accession = exp.get("accession")
            assay = exp.get("assay_title")
            target = (exp.get("target") or {}).get("label", "")
            biosample_id = (exp.get("biosample_ontology") or {}).get("term_id")
            biosample_cell = (exp.get("biosample_ontology") or {}).get("term_name")

            description = exp.get("description")
            health_status = exp.get("health_status")
            exp_url = "https://www.encodeproject.org" + exp.get("@id", "")

            for f in exp.get("files", []):
                if f.get("output_type") in [
                    "IDR thresholded peaks",
                    "pseudoreplicated peaks",
                ]:
                    reps = f.get("biological_replicates", [])
                    if reps != [1, 2]:
                        continue

                rows.append(
                    {
                        "study_id": exp_accession,
                        "title": f"{assay} - {target}",
                        "overall_description": description,
                        "reference": exp_url,
                        "status": health_status,
                        "biosample_summary": f.get("simple_biosample_summary"),
                        "biosample_term_id": biosample_id,
                        "platform": "-",
                        "sample": biosample_cell,
                        "submitted_data_accession": f.get("accession"),
                        "submitted_data_type": f.get("file_type"),
                        "submitted_data_output_type": f.get("output_type"),
                        "submitted_data_assembly": f.get("assembly"),
                        "file_status": f.get("status"),
                        "replicates": ",".join(
                            map(str, f.get("biological_replicates", []))
                        ),
                        "download_url": "https://www.encodeproject.org"
                        + f.get("href", ""),
                    }
                )
        return rows

    def _filter_dataframe(self, rows):
        df = pd.DataFrame(rows)
        df = df[df.submitted_data_output_type.isin(["IDR thresholded peaks"])]
        df = df[df.submitted_data_type.isin(["bed narrowPeak"])]
        return df

    def _convert_file_to_profiling_format(self, url: str, output_path: str) -> str:
        """
        Download a narrowPeak file and convert it into ProfilingRecord schema format.
        Keeps only: #chrom, start, end, name, score, strand, me (-log10FDR from q-value).
        """
        resp = requests.get(url, headers={"Accept": "text/plain"})
        resp.raise_for_status()

        lines = []
        for line in resp.text.strip().splitlines():
            cols = line.split("\t")
            if len(cols) < 9:
                continue  # skip malformed rows
            chrom = cols[0]
            start = cols[1]
            end = cols[2]
            name = cols[3]
            score = cols[4]
            strand = cols[5] if cols[5] in ["+", "-", "."] else "."
            me = cols[8]  # q-value column = -log10FDR

            lines.append([chrom, start, end, name, score, strand, me])

        df = pd.DataFrame(
            lines,
            columns=["#chrom", "start", "end", "name", "score", "strand", "me"],
        )

        df.to_csv(output_path, sep="\t", index=False)
        return output_path

    @transaction.atomic
    def _create_profiling_study(self, row):
        # --- Convert and save BED file locally ---
        with tempfile.NamedTemporaryFile(suffix=".bed", delete=False) as tmp:
            converted_file = self._convert_file_to_profiling_format(
                row["download_url"], tmp.name
            )

        # --- ProfilingStudy ---
        ProfilingStudy.objects.update_or_create(
            study_id=row["study_id"],
            defaults={
                "title": row["title"],
                "reference": row["reference"],
                "overall_description": row["overall_description"] or "",
                "biosample": None,
                "platform": None,
                "sample": None,
                # no StudyData here, signals will attach it
            },
        )
