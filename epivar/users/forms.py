from django import forms
from django.contrib.auth.forms import BaseUserCreationForm

from .models import User


class SignUpForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "institution", "password1", "password2")


class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email", "institution")
