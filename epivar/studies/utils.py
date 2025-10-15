from django.apps import apps
from django_celery_results.models import TaskResult

from .models import IntegrationStatus


def update_integration_status(model_name, instance_id, task_id, integration_status):
    model_class = apps.get_model("studies", model_name)
    instance = model_class.objects.get(id=instance_id)
    task = TaskResult.objects.get(task_id=task_id)

    if integration_status != IntegrationStatus.FAILED:
        instance.integration_task = task
        instance.integration_status = integration_status
        instance.save(update_fields=["integration_task", "integration_status"])

    else:
        instance.integration_status = integration_status
        instance.save(update_fields=["integration_status"])
