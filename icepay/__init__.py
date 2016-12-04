from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from pretix import __version__ as version


class IcepayApp(AppConfig):
    name = 'pretix.plugins.icepay'
    verbose_name = _("Icepay")

    class PretixPluginMeta:
        name = _("Icepay")
        author = _("the pretix team")
        version = version
        description = _("This plugin allows you to receive credit card payments " +
                        "via Icepay")

        from . import signals  # NOQA

    @cached_property
    def compatibility_errors(self):
        errs = []
        try:
            import stripe  # NOQA
        except ImportError:
            errs.append("Python package 'stripe' is not installed.")
        return errs

default_app_config = 'pretix.plugins.icepay.IcepayApp'
