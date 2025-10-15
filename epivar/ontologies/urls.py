from django.urls import path
from .views import TermCreatePopup

urlpatterns = [
    path("add-term/<str:category>/", TermCreatePopup.as_view(), name="add-term"),
]
