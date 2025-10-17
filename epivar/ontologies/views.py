from django.contrib import messages
from django_addanother.views import CreatePopupMixin
from django.views.generic.edit import CreateView
from django.core.exceptions import ValidationError
from .models import Term


class TermCreatePopup(CreatePopupMixin, CreateView):
    model = Term
    template_name = "ontologies/create_term.html"
    fields = ["obo_id", "category"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["category"].disabled = True
        return form

    def get_initial(self):
        initial = super().get_initial()

        if "category" in self.kwargs:
            initial["category"] = self.kwargs["category"]

        return initial

    def form_valid(self, form):
        obo_id = form.cleaned_data.get("obo_id")
        try:
            form.save(commit=True)
            return super().form_valid(form)

        except ValidationError:
            messages.error(
                self.request,
                f"{obo_id} is not a valid ontology ID or cannot be fetched from OLS!",
            )
            # Re-render form with error message
            return self.form_invalid(form)
