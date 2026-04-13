from django import forms
from django.db.models import Q
from django.forms import formset_factory
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Item, ItemCategory, SubEvent
from pretix.control.forms.widgets import Select2


class MultiTicketSettingsForm(forms.Form):
    separate_orders = forms.BooleanField(
        required=False,
        label=_("Eigene Bestellung"),
        help_text=_("Wenn aktiv, wird jede Zeile als eigene Bestellung erstellt."),
    )
    order_comment = forms.CharField(
        required=False,
        label=_("Order comment"),
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": _("Add comment"),
            }
        ),
    )


class MultiTicketRowForm(forms.Form):
    category = forms.ModelChoiceField(
        label=_("Category"),
        queryset=ItemCategory.objects.none(),
        required=False,
        empty_label=_("All categories"),
    )
    product = forms.ModelChoiceField(
        label=_("Ticket type"),
        queryset=Item.objects.none(),
        required=True,
    )
    ticket_date = forms.ModelChoiceField(
        label=_("Date"),
        queryset=SubEvent.objects.none(),
        required=False,
        empty_label=_("All dates"),
    )
    ticket_count = forms.IntegerField(label=_("Ticket count"), min_value=1, initial=1)
    personalized = forms.BooleanField(required=False, label=_("Personalisiert"))
    attendee_email = forms.EmailField(required=False, label=_("E-Mail"))
    attendee_first_name = forms.CharField(required=False, label=_("Vorname"))
    attendee_last_name = forms.CharField(required=False, label=_("Nachname"))
    attendee_company = forms.CharField(required=False, label=_("Firma"))
    free_ticket = forms.BooleanField(required=False, label=_("Freikarte"))

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event")
        super().__init__(*args, **kwargs)

        has_sub_events = event.has_subevents
        sub_events = None
        if has_sub_events:
            sub_events = event.subevents.values_list("id", flat=True)

        if sub_events:
            products = Item.objects.filter(
                Q(event_id__in=list(sub_events)) | Q(event=event)
            ).exclude(seat_category_mappings__isnull=False)
        else:
            products = Item.objects.filter(Q(event=event)).exclude(
                seat_category_mappings__isnull=False
            )

        self.fields["category"].widget = Select2(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "plugins:pretix_i_ticket_multiticket_generator:multiticket_generator.categories.select2",
                    kwargs={
                        "event": event.slug,
                        "organizer": event.organizer.slug,
                    },
                ),
                "data-placeholder": _("All categories"),
            }
        )
        self.fields["product"].widget = Select2(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "plugins:pretix_i_ticket_multiticket_generator:multiticket_generator.items.select2",
                    kwargs={
                        "event": event.slug,
                        "organizer": event.organizer.slug,
                        "category": 0,
                    },
                ),
                "data-placeholder": _("All products"),
            }
        )
        self.fields["ticket_date"].widget = Select2(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "plugins:pretix_i_ticket_multiticket_generator:multiticket_generator.subevents.select2",
                    kwargs={
                        "event": event.slug,
                        "organizer": event.organizer.slug,
                    },
                ),
                "data-placeholder": _("All Subevents"),
            }
        )
        self.fields["category"].queryset = event.categories.all()
        self.fields["product"].queryset = products
        self.fields["ticket_date"].queryset = event.subevents.all()
        if not event.settings.attendee_company_asked:
            self.fields.pop("attendee_company")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("personalized"):
            if not cleaned.get("attendee_first_name"):
                self.add_error(
                    "attendee_first_name", _("Vorname ist bei personalisiert Pflicht.")
                )
            if not cleaned.get("attendee_last_name"):
                self.add_error(
                    "attendee_last_name", _("Nachname ist bei personalisiert Pflicht.")
                )
        return cleaned


def build_ticket_row_formset(event, data=None):
    RowForm = formset_factory(
        MultiTicketRowForm,
        extra=0,
        can_delete=False,
        min_num=1,
        validate_min=True,
    )
    kwargs = {
        "data": data,
        "prefix": "rows",
        "form_kwargs": {"event": event},
    }
    if data is None:
        kwargs["initial"] = [{}]
    return RowForm(
        **kwargs,
    )
