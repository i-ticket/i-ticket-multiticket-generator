from django.urls import re_path

from .views import IndexView, categories_select2, products_select2, subevents_select2

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/tickets/create/multi$",
        IndexView.as_view(),
        name="multiticket_generator_index",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/(?P<category>[^/]+)/items$",
        products_select2,
        name="multiticket_generator.items.select2",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/sub-events$",
        subevents_select2,
        name="multiticket_generator.subevents.select2",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/categories$",
        categories_select2,
        name="multiticket_generator.categories.select2",
    ),
]
