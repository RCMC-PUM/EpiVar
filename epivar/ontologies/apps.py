from django.apps import AppConfig


class OntologiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ontologies"

    def ready(self):
        from . import signals
