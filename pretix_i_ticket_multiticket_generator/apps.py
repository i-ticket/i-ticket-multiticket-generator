from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = "pretix_i_ticket_multiticket_generator"
    verbose_name = "i-ticket Multiticket Generator"

    class PretixPluginMeta:
        name = gettext_lazy("i-ticket Multiticket Generator")
        author = "i-ticket"
        description = gettext_lazy("Create multiple tickets/orders in one step")
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2.7.0"

    def ready(self):
        from . import signals  # NOQA
