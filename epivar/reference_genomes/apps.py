from django.apps import AppConfig


class ReferenceGenomesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reference_genomes"

    def ready(self):
        from . import signals
