from pathlib import Path
from tqdm import tqdm
import json

from django.core.management.base import BaseCommand
from reference_genomes.models import GeneSet, GeneSetCollection


class Command(BaseCommand):
    help = "Import Human MSigDB Collections"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            type=str,
            help="Path to the directory comprising JSON metadata file(s)",
        )

    def handle(self, *args, **options):
        json_dir = Path(options["dir"])

        if not json_dir.is_dir():
            return

        json_files = [f for f in json_dir.glob("*.json") if "all" in f.name]

        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                gene_sets = json.load(f)

            for name, elements in tqdm(gene_sets.items()):
                collection_parts = elements.get("collection", "").split(":")
                gene_data = {
                    "name": name,
                    "collection": (
                        collection_parts[0] if len(collection_parts) > 0 else None
                    ),
                    "subcollection": (
                        collection_parts[1] if len(collection_parts) > 1 else None
                    ),
                    "subset": (
                        collection_parts[2] if len(collection_parts) > 2 else None
                    ),
                    "systematic_name": elements.get("systematicName"),
                    "pmid": elements.get("pmid"),
                    "exact_source": elements.get("exactSource"),
                    "external_details_url": elements.get("externalDetailsURL"),
                    "reference": f"The Molecular Signatures Database (MSigDB)",
                    "reference_url": elements.get("msigdbURL"),
                    "genes": {"genes": elements.get("geneSymbols")},
                }

                # Remove None values to avoid passing unnecessary kwargs
                gene_data_clean = {k: v for k, v in gene_data.items() if v is not None}

                try:
                    GeneSet.objects.get_or_create(**gene_data_clean)

                except Exception as e:
                    print(e)
                    print(gene_data_clean)
