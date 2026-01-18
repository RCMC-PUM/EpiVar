from django.conf import settings
from django_minio_backend.models import MinioBackend


def get_public_storage():
    return MinioBackend(
        bucket_name=settings.MINIO_STATIC_BUCKET,
        storage_name='default',
    )


def get_private_storage():
    return MinioBackend(
        bucket_name=settings.MINIO_DEFAULT_BUCKET,
        storage_name='default',
    )
