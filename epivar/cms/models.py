import uuid
import os

from django.db import models
from django.utils.timezone import now
from tinymce import models as tinymce_models


class Document(models.Model):
    name = models.SlugField(primary_key=True)
    creation_date = models.DateTimeField(default=now)
    content = tinymce_models.HTMLField(null=True, blank=True)


def logo_upload_path(instance, filename):
    # store as consortium_members/logos/<uuid>.<ext>
    ext = os.path.splitext(filename)[1].lower()
    return f"consortium_members/logos/{uuid.uuid4()}{ext}"


class ConsortiumMember(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    institution = models.CharField(max_length=255)
    logo = models.ImageField(
        upload_to=logo_upload_path,
        blank=True,
        null=True,
        help_text="Upload institution logo (PNG/JPG/SVG).",
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.institution})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
