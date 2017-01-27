from django.apps import AppConfig
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _


class IcepayApp(AppConfig):
    name = 'pretix_icepay'
    verbose_name = _('Icepay')

    class PretixPluginMeta:
        name = _('Icepay')
        author = _('the SHA2017 team')
        version = '0.0.1'
        description = _(
            'This plugin allows you to receive IDEAL payments via Icepay')

    def ready(self):
        from . import signals  # NOQA

    @cached_property
    def compatibility_errors(self):
        errs = []
        try:
            import icepay # NOQA
        except ImportError:
            errs.append('Required package "icepay-python" is not installed.')
        return errs


default_app_config = 'pretix_icepay.IcepayApp'
