import json

from django.core.urlresolvers import resolve
from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from pretix.base.signals import logentry_display, register_payment_providers
from pretix.presale.signals import html_head


@receiver(register_payment_providers, dispatch_uid="payment_stripe")
def register_payment_provider(sender, **kwargs):
    from .payment import Stripe

    return Stripe


@receiver(html_head, dispatch_uid="payment_stripe_html_head")
def html_head_presale(sender, request=None, **kwargs):
    from .payment import Stripe

    provider = Stripe(sender)
    url = resolve(request.path_info)
    if provider.is_enabled and ("checkout" in url.url_name or "order.pay" in url.url_name):
        template = get_template('pretixplugins/stripe/presale_head.html')
        ctx = {'event': sender, 'settings': provider.settings}
        return template.render(ctx)
    else:
        return ""


@receiver(signal=logentry_display, dispatch_uid="stripe_logentry_display")
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type != 'pretix.plugins.stripe.event':
        return

    data = json.loads(logentry.data)
    event_type = data.get('type')
    text = None
    plains = {
        'charge.succeeded': _('Charge succeeded.'),
        'charge.refunded': _('Charge refunded.'),
        'charge.updated': _('Charge updated.'),
    }

    if event_type in plains:
        text = plains[event_type]
    elif event_type == 'charge.failed':
        text = _('Charge failed. Reason: {}').format(data['data']['object']['failure_message'])
    elif event_type == 'charge.dispute.created':
        text = _('Dispute created. Reason: {}').format(data['data']['object']['reason'])
    elif event_type == 'charge.dispute.updated':
        text = _('Dispute updated. Reason: {}').format(data['data']['object']['reason'])
    elif event_type == 'charge.dispute.closed':
        text = _('Dispute closed. Status: {}').format(data['data']['object']['status'])

    if text:
        return _('Stripe reported an event: {}').format(text)
