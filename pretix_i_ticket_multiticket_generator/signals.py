from django.dispatch import receiver
from django.urls import NoReverseMatch, resolve, reverse
from django.utils.translation import gettext_lazy as _

from pretix.control.signals import nav_event


@receiver(nav_event, dispatch_uid="multiticket-generator-nav")
def control_nav_import(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
        request.organizer, request.event, "can_view_orders", request=request
    ):
        return []

    try:
        parent_url = reverse(
            "plugins:pretix_i_ticket_ticket_generator:ticket_generator_index",
            kwargs={
                "event": request.event.slug,
                "organizer": request.event.organizer.slug,
            },
        )
    except NoReverseMatch:
        parent_url = reverse(
            "control:event.orders",
            kwargs={
                "event": request.event.slug,
                "organizer": request.event.organizer.slug,
            },
        )

    return [
        {
            "label": _("Multi Ticket(s) erstellen"),
            "url": reverse(
                "plugins:pretix_i_ticket_multiticket_generator:multiticket_generator_index",
                kwargs={
                    "event": request.event.slug,
                    "organizer": request.organizer.slug,
                },
            ),
            "parent": parent_url,
            "active": url.namespace == "plugins:pretix_i_ticket_multiticket_generator",
            "icon": "plus-square",
        }
    ]
