from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    institution = models.CharField(max_length=255, null=False)
    is_reviewer = models.BooleanField(default=False)
    # TODO add token
