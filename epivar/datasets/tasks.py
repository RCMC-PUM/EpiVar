import hashlib
from celery import shared_task
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist


def calculate_md5(file_obj):
    """Calculate md5 checksum for a file-like object."""
    md5 = hashlib.md5()
    for chunk in iter(lambda: file_obj.read(64 * 1024), b""):
        md5.update(chunk)
    return md5.hexdigest()


@shared_task(bind=True, max_retries=3)
def update_file_checksum_task(
    self, app_label, model_name, object_id, file_field_name, checksum_field_name
):
    """
    Celery task: calculate checksum of a file field and update checksum field.

    Args:
        app_label (str): Django app label.
        model_name (str): Model name.
        object_id (int): Primary key of the object.
        file_field_name (str): Name of the FileField.
        checksum_field_name (str): Name of the checksum CharField.
    """
    try:
        Model = apps.get_model(app_label, model_name)

        # Get only the file path (avoid loading whole instance)
        file_path = (
            Model.objects.filter(pk=object_id)
            .values_list(file_field_name, flat=True)
            .first()
        )

        if not file_path:
            return f"No file found in field '{file_field_name}' for {model_name}({object_id})"

        # Access storage backend and stream the file
        field = Model._meta.get_field(file_field_name)
        with field.storage.open(file_path, "rb") as f:
            checksum = calculate_md5(f)

        # Update the checksum field directly in the database
        updated = Model.objects.filter(pk=object_id).update(
            **{checksum_field_name: checksum}
        )
        if not updated:
            raise ObjectDoesNotExist(
                f"Object {model_name} with id={object_id} not found"
            )

        return f"Checksum updated for {model_name}({object_id})"

    except ObjectDoesNotExist:
        return f"Object {model_name} with id={object_id} not found"

    except Exception as exc:
        # Retry in case of transient errors
        raise self.retry(exc=exc, countdown=10)
