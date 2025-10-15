import os
import json
from tqdm import tqdm
from django.apps import apps

print(apps.get_app_config("ontologies").path)

from django.core.management.base import BaseCommand

# from datasets.models import ClinicalAssociationStudy


class Command(BaseCommand):
    help = "Import CHiP-seq data from ENCODE"

    def handle(self, *args, **options):
        pass
