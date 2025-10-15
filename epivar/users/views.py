from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordChangeView,
)
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy

from django.contrib.auth.forms import PasswordResetForm
from .forms import SignUpForm, UpdateProfileForm
from .models import User


class SignUpView(CreateView):
    model = User
    form_class = SignUpForm
    template_name = "users/sign_up.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)

        messages.success(self.request, "Account created successfully!")
        return redirect(self.get_success_url())


class SignInView(LoginView):
    model = User
    template_name = "users/sign_in.html"

    def form_valid(self, form):
        messages.success(self.request, "Logged in successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("home")


class ResetPasswordView(PasswordResetView):
    model = User
    template_name = "users/reset_password.html"
    email_template_name = "users/password_reset_email.html"
    subject_template_name = "users/password_reset_subject.txt"

    form_class = PasswordResetForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        messages.success(
            self.request, "A password reset link has been sent to your email."
        )
        return super().form_valid(form)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UpdateProfileForm
    template_name = "users/update_profile.html"

    def get_success_url(self):
        return self.request.path

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    context_object_name = "password_form"
    template_name = "users/update_password.html"

    def get_success_url(self):
        return self.request.path

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed successfully.")
        return super().form_valid(form)


class SignOutView(LogoutView):
    model = User
    next_page = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, "You have logged out.")
        return super().dispatch(request, *args, **kwargs)
