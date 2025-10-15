from django.shortcuts import render
from .models import Document, ConsortiumMember


# Create your views here.
def documentation(request):
    context = {
        "title": "Documentation",
        "document": Document.objects.filter(name="documentation").first(),
    }
    return render(request, "cms/document.html", context)


def terms(request):
    context = {
        "title": "Terms and Conditions",
        "document": Document.objects.filter(name="terms").first(),
    }
    return render(request, "cms/document.html", context)


def consortium_members(request):
    context = {
        "title": "Consortium Members",
        "members": ConsortiumMember.objects.all(),
    }
    return render(request, "cms/members.html", context)
