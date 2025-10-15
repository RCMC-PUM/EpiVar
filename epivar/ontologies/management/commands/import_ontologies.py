import os
import json
from tqdm import tqdm
from django.apps import apps

print(apps.get_app_config("ontologies").path)

from django.core.management.base import BaseCommand
from ontologies.models import Term, TermCategory


class Command(BaseCommand):
    help = "Import ontologies from JSON file"

    def handle(self, *args, **options):
        file_path = os.path.join(
            apps.get_app_config("ontologies").path,
            "management",
            "commands",
            "ontologies.json",
        )
        with open(file_path, "r") as handle:
            ontologies = json.load(handle)

        categories = set([key.upper() for key in ontologies.keys()])
        unmatched_categories = categories.difference(set(TermCategory._member_names_))
        if unmatched_categories:
            assert (
                False
            ), f"Declared category(ies) {unmatched_categories} not found in DB"

        for category, records in ontologies.items():
            for record in tqdm(set(records), desc=category):
                if Term.objects.filter(obo_id=record).first():
                    continue

                instance = Term(obo_id=record, category=category)
                instance.save()
