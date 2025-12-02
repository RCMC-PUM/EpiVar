import os.path
from pathlib import Path
from typing import Dict, Any, Tuple, Iterable

from tqdm import tqdm
import json

from django.core.management.base import BaseCommand
from reference_genomes.models import GeneSet, GeneSetCollection  # noqa


class Command(BaseCommand):
    help = "Import Human MSigDB Collections from JSON files"
    REFERENCE = "The Molecular Signatures Database (MSigDB)"

    # -----------------------
    # Helpers methods
    # -----------------------

    def _load_gene_sets(self, json_file: Path) -> Dict[str, Dict[str, Any]]:
        """
        Load gene set data from a JSON file.
        """
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                self.stderr.write(f"Unexpected JSON structure in {json_file}, expected object at root.")
                return {}

            return data

        except (OSError, json.JSONDecodeError) as exc:
            self.stderr.write(f"Failed to read {json_file}: {exc}")
            return {}

    @staticmethod
    def _parse_collection(collection: str | None) -> Tuple[str | None, str | None, str | None]:
        """
        Parse the collection string into (collection, subcollection, subset).
        Input format expected: 'COLLECTION:SUBCOLLECTION:SUBSET'.
        """
        if not collection:
            return None, None, None

        parts = collection.split(":")
        collection_val = parts[0] if len(parts) > 0 else None
        subcollection_val = parts[1] if len(parts) > 1 else None
        subset_val = parts[2] if len(parts) > 2 else None

        return collection_val, subcollection_val, subset_val

    def _build_gene_data(self, name: str, elements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the kwargs dict for GeneSet.objects.get_or_create(), removing None values.
        """
        collection, subcollection, subset = self._parse_collection(elements.get("collection"))

        gene_data = {
            "name": name,
            "collection": getattr(GeneSetCollection, collection),
            "subcollection": subcollection,
            "subset": subset,
            "systematic_name": elements.get("systematicName"),
            "pmid": elements.get("pmid"),
            "exact_source": elements.get("exactSource"),
            "external_details_url": elements.get("externalDetailsURL"),
            "reference": self.REFERENCE,
            "reference_url": elements.get("msigdbURL"),
            "genes": {"genes": elements.get("geneSymbols")},
        }

        # Remove None values to avoid passing unnecessary kwargs
        return {k: v for k, v in gene_data.items() if v is not None}

    def _create_gene_sets(self, gene_sets: Dict[str, Dict[str, Any]]) -> None:
        """
        Iterate over parsed gene set definitions and persist them using get_or_create.
        """
        iterable = gene_sets.items()
        for name, elements in tqdm(iterable, total=len(gene_sets), desc="Importing gene sets"):
            gene_data_clean = self._build_gene_data(name, elements)

            try:
                GeneSet.objects.get_or_create(**gene_data_clean)
            except Exception as exc:  # noqa
                self.stderr.write(f"Error creating GeneSet {name}: {exc}")
                self.stderr.write(str(gene_data_clean))

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the msigdb JSON file",
        )

    def handle(self, *args, **options) -> None:
        json_file = Path(options["file"])

        if not os.path.exists(json_file):
            self.stderr.write(f"Provided file does not exists: {json_file}")
            return

        gene_sets = self._load_gene_sets(json_file)
        if not gene_sets:
            self.stderr.write(f"Cannot parse gene sets from: {json_file}")
            return

        self._create_gene_sets(gene_sets)

