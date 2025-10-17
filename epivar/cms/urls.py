from django.urls import path, include
from .views import documentation, consortium_members, terms

urlpatterns = [
    path("tinymce/", include("tinymce.urls")),
    path("documentation/", documentation, name="documentation"),
    path("consortium-members/", consortium_members, name="consortium-members"),
    path("terms-and-conditions", terms, name="terms-and-conditions"),
]
