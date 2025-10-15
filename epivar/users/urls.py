from django.urls import path
from .views import (
    SignUpView,
    SignInView,
    SignOutView,
    ResetPasswordView,
    ProfileUpdateView,
    CustomPasswordChangeView,
)

urlpatterns = [
    path("sign_up/", SignUpView.as_view(), name="sign-up"),
    path("sign_in/", SignInView.as_view(), name="sign-in"),
    path("sign_out/", SignOutView.as_view(), name="sign-out"),
    path("reset_password/", ResetPasswordView.as_view(), name="reset-password"),
    path("update_profile/", ProfileUpdateView.as_view(), name="update-profile"),
    path(
        "change_password/", CustomPasswordChangeView.as_view(), name="change-password"
    ),
]
