from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ("username", "email", "institution", "is_reviewer", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Reviewer",
            {
                "fields": ("is_reviewer",),
            },
        ),
    )
