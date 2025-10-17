import logging

import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import AnatomicalStructure, CellType, Term

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AnatomicalStructure)
@receiver(post_save, sender=CellType)
@receiver(post_save, sender=Term)
def fetch_ontology_data(sender, instance, **kwargs):
    obo_id = instance.obo_id
    url = f"https://www.ebi.ac.uk/ols4/api/terms/findByIdAndIsDefiningOntology?id={obo_id}&lang=en"

    response = requests.get(url)
    if response.status_code != 200:
        logger.error(
            f"Failed to fetch term {obo_id}. HTTP Status: {response.status_code}"
        )
        return

    data = response.json()
    if data.get("page", {}).get("totalElements", 0) == 0:
        instance.delete()
        raise ValidationError(f"Term {obo_id} not found.")

    term = data["_embedded"]["terms"][0]
    type(instance).objects.filter(pk=instance.pk).update(
        iri=term.get("iri"),
        label=term.get("label"),
        synonyms=" | ".join(term.get("synonyms") or []),
        description=" | ".join(term.get("description") or []),
        ontology_name=term.get("ontology_name"),
    )

    logger.info(f"Term {obo_id} updated successfully")
