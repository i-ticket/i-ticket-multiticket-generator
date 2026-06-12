from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from rest_framework.exceptions import ValidationError

from pretix.api.serializers.order import OrderCreateSerializer
from pretix.base.i18n import language
from pretix.base.models import Item, Order, TaxRule
from pretix.base.settings import PERSON_NAME_SCHEMES
from pretix.base.services.invoices import generate_invoice, invoice_qualified
from pretix.base.services.orders import _order_placed_email, _order_placed_email_attendee
from pretix.base.signals import order_paid, order_placed
from pretix.control.permissions import event_permission_required

from .forms import MultiTicketSettingsForm, build_ticket_row_formset


class IndexView(FormView):
    template_name = "pretix_i_ticket_multiticket_generator/index.html"
    permission = ["can_change_orders", "can_change_event_settings"]
    form_class = MultiTicketSettingsForm

    def get_success_url(self):
        return reverse(
            "plugins:pretix_i_ticket_multiticket_generator:multiticket_generator_index",
            kwargs={
                "organizer": self.request.event.organizer.slug,
                "event": self.request.event.slug,
            },
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "row_formset" not in ctx:
            ctx["row_formset"] = build_ticket_row_formset(self.request.event)
        ctx["subevents"] = self.request.event.subevents
        return ctx

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        row_formset = build_ticket_row_formset(request.event, data=request.POST)
        if form.is_valid() and row_formset.is_valid():
            return self._handle_valid_submission(form, row_formset)

        return self.render_to_response(
            self.get_context_data(form=form, row_formset=row_formset)
        )

    def _handle_valid_submission(self, form, row_formset):
        rows = [
            f.cleaned_data
            for f in row_formset.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE")
        ]
        if not rows:
            messages.error(self.request, _("Bitte mindestens eine Ticket-Zeile anlegen."))
            return self.render_to_response(
                self.get_context_data(form=form, row_formset=row_formset)
            )

        separate_orders = form.cleaned_data.get("separate_orders", False)
        order_comment = form.cleaned_data.get("order_comment", "")
        if separate_orders:
            has_row_errors = False
            for row_form in row_formset.forms:
                row_data = getattr(row_form, "cleaned_data", None) or {}
                if not row_data:
                    continue
                attendee_email = (row_data.get("attendee_email") or "").strip()
                if not attendee_email:
                    row_form.add_error(
                        "attendee_email",
                        _("Bei 'Eigene Bestellung' ist E-Mail pro Zeile Pflicht."),
                    )
                    has_row_errors = True
            if has_row_errors:
                return self.render_to_response(
                    self.get_context_data(form=form, row_formset=row_formset)
                )
            contact_email = ""
        else:
            first_form = row_formset.forms[0] if row_formset.forms else None
            first_row_email = (
                ((rows[0].get("attendee_email") if rows else "") or "").strip()
            )
            if not first_row_email:
                if first_form:
                    first_form.add_error(
                        "attendee_email",
                        _("In Zeile 1 ist E-Mail Pflicht."),
                    )
                return self.render_to_response(
                    self.get_context_data(form=form, row_formset=row_formset)
                )
            contact_email = first_row_email
        created_orders = 0
        created_positions = 0

        try:
            with transaction.atomic():
                if separate_orders:
                    for row in rows:
                        payload = self._build_order_payload(
                            [row],
                            order_comment=order_comment,
                            contact_email=(row.get("attendee_email") or "").strip(),
                        )
                        order = self._create_order(payload, order_comment)
                        created_orders += 1
                        created_positions += order.positions.count()
                else:
                    payload = self._build_order_payload(
                        rows,
                        order_comment=order_comment,
                        contact_email=contact_email,
                    )
                    order = self._create_order(payload, order_comment)
                    created_orders = 1
                    created_positions = order.positions.count()
        except Exception as e:
            messages.error(
                self.request,
                _("Es gab ein Problem bei der Erstellung der Bestellung: %(error)s")
                % {"error": str(e)},
            )
            return self.render_to_response(
                self.get_context_data(form=form, row_formset=row_formset)
            )

        messages.success(
            self.request,
            _(
                "Erfolgreich erstellt: %(orders)s Bestellung(en), %(tickets)s Ticket(s)."
            )
            % {
                "orders": created_orders,
                "tickets": created_positions,
            },
        )
        return redirect(self.get_success_url())

    def _attendee_name_parts(self, first_name, last_name):
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        scheme_name = self.request.event.settings.name_scheme
        scheme = PERSON_NAME_SCHEMES.get(scheme_name, PERSON_NAME_SCHEMES["given_family"])
        asked_keys = [k for (k, _label, _width) in scheme["fields"]]

        parts = {"_scheme": scheme_name}
        if "given_name" in asked_keys:
            parts["given_name"] = first_name
        if "family_name" in asked_keys:
            parts["family_name"] = last_name
        if "full_name" in asked_keys and "given_name" not in asked_keys:
            parts["full_name"] = f"{first_name} {last_name}".strip()
        if "calling_name" in asked_keys:
            parts["calling_name"] = first_name
        return parts

    def _build_order_payload(self, rows, order_comment="", contact_email=""):
        order_positions = []
        position_id = 1
        event_locales = list(self.request.event.settings.locales or [])
        event_locale = self.request.event.settings.locale
        if event_locale not in event_locales and event_locales:
            event_locale = event_locales[0]
        if not event_locale:
            event_locale = "en"
        contact_email = (contact_email or "").strip()

        for row in rows:
            ticket_count = row.get("ticket_count") or 1
            product = row.get("product")
            subevent = row.get("ticket_date")
            personalized = row.get("personalized")
            name_mode = row.get("name_mode") or "same"
            attendee_email = row.get("attendee_email")
            attendee_first_name = (row.get("attendee_first_name") or "").strip()
            attendee_last_name = (row.get("attendee_last_name") or "").strip()
            attendee_company = (row.get("attendee_company") or "").strip()
            attendee_names = row.get("attendee_names") or []
            free_ticket = row.get("free_ticket")

            for ticket_idx in range(ticket_count):
                position = {
                    "positionid": position_id,
                    "item": product.id,
                    "variation": None,
                    "price": Decimal("0.00") if free_ticket else None,
                    "seat": None,
                    "subevent": subevent.id if subevent else None,
                }
                if personalized:
                    if name_mode == "individual" and attendee_names:
                        name_entry = attendee_names[ticket_idx]
                        first_name = (name_entry.get("first_name") or "").strip()
                        last_name = (name_entry.get("last_name") or "").strip()
                    else:
                        first_name = attendee_first_name
                        last_name = attendee_last_name
                    position["attendee_name_parts"] = self._attendee_name_parts(
                        first_name, last_name
                    )
                    if attendee_company:
                        position["company"] = attendee_company
                if attendee_email:
                    position["attendee_email"] = attendee_email
                order_positions.append(position)
                position_id += 1

        return {
            "email": contact_email,
            "locale": event_locale,
            "positions": order_positions,
            "force": True,
            "sales_channel": "web",
            "comment": order_comment or "",
        }

    def _create_order(self, order_data, order_comment):
        serializer = OrderCreateSerializer(
            data=order_data,
            context=dict(event=self.request.event, request=self.request),
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(comment=order_comment)
        except TaxRule.SaleNotAllowed:
            raise ValidationError(
                _("One of the selected products is not available in the selected country.")
            )

        order = serializer.instance
        order.log_action(
            "pretix.event.order.placed",
            user=self.request.user if self.request.user.is_authenticated else None,
            auth=None,
        )

        with language(order.locale, self.request.event.settings.region):
            payment = order.payments.last()
            order_placed.send(self.request.event, order=order)
            if order.status == Order.STATUS_PAID:
                order_paid.send(self.request.event, order=order)
                order.log_action(
                    "pretix.event.order.paid",
                    {
                        "provider": payment.provider if payment else None,
                        "info": {},
                        "date": now().isoformat(),
                        "force": False,
                    },
                    user=self.request.user if self.request.user.is_authenticated else None,
                    auth=None,
                )

            gen_invoice = invoice_qualified(order) and (
                (order.event.settings.get("invoice_generate") == "True")
                or (
                    order.event.settings.get("invoice_generate") == "paid"
                    and order.status == Order.STATUS_PAID
                )
            ) and not order.invoices.last()
            invoice = generate_invoice(order, trigger_pdf=True) if gen_invoice else None

            free_flow = (
                payment
                and order.total == Decimal("0.00")
                and order.status == Order.STATUS_PAID
                and not order.require_approval
                and payment.provider in ("free", "boxoffice")
            )
            if order.require_approval:
                email_template = self.request.event.settings.mail_text_order_placed_require_approval
                subject_template = self.request.event.settings.mail_subject_order_placed_require_approval
                log_entry = "pretix.event.order.email.order_placed_require_approval"
                email_attendees = False
            elif free_flow:
                email_template = self.request.event.settings.mail_text_order_free
                subject_template = self.request.event.settings.mail_subject_order_free
                log_entry = "pretix.event.order.email.order_free"
                email_attendees = self.request.event.settings.mail_send_order_free_attendee
                email_attendees_template = self.request.event.settings.mail_text_order_free_attendee
                subject_attendees_template = self.request.event.settings.mail_subject_order_free_attendee
            else:
                email_template = self.request.event.settings.mail_text_order_placed
                subject_template = self.request.event.settings.mail_subject_order_placed
                log_entry = "pretix.event.order.email.order_placed"
                email_attendees = self.request.event.settings.mail_send_order_placed_attendee
                email_attendees_template = self.request.event.settings.mail_text_order_placed_attendee
                subject_attendees_template = self.request.event.settings.mail_subject_order_placed_attendee

            _order_placed_email(
                self.request.event,
                order,
                email_template,
                subject_template,
                log_entry,
                invoice,
                [payment] if payment else [],
                is_free=free_flow,
            )
            if email_attendees:
                for p in order.positions.all():
                    if p.addon_to_id is None and p.attendee_email and p.attendee_email != order.email:
                        _order_placed_email_attendee(
                            self.request.event,
                            order,
                            p,
                            email_attendees_template,
                            subject_attendees_template,
                            log_entry,
                            is_free=free_flow,
                        )

            if not free_flow and order.status == Order.STATUS_PAID and payment:
                payment._send_paid_mail(invoice, None, "")
                if self.request.event.settings.mail_send_order_paid_attendee:
                    for p in order.positions.all():
                        if p.addon_to_id is None and p.attendee_email and p.attendee_email != order.email:
                            payment._send_paid_mail_attendee(p, None)

        return order


@event_permission_required(None)
def categories_select2(request, **kwargs):
    categories = request.event.categories.all()
    return JsonResponse(
        {
            "results": [{"id": item.pk, "text": str(item)} for item in categories],
        }
    )


@event_permission_required(None)
def products_select2(request, **kwargs):
    has_sub_events = request.event.has_subevents
    sub_events = None
    if has_sub_events:
        sub_events = request.event.subevents.values_list("id", flat=True)

    category_id = int(kwargs.get("category"))

    if sub_events:
        products = Item.objects.filter(
            Q(event_id__in=list(sub_events)) | Q(event=request.event)
        ).exclude(seat_category_mappings__isnull=False)
    else:
        products = Item.objects.filter(Q(event=request.event)).exclude(
            seat_category_mappings__isnull=False
        )

    if category_id > 0:
        products = products.filter(category_id=category_id)

    return JsonResponse(
        {
            "results": [{"id": item.pk, "text": str(item)} for item in products],
        }
    )


@event_permission_required(None)
def subevents_select2(request, **kwargs):
    qs = request.event.subevents.all()
    if not qs:
        qs = [request.event]
    return JsonResponse(
        {
            "results": [{"id": item.pk, "text": str(item)} for item in qs],
        }
    )
