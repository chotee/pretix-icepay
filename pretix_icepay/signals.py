import json

from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from pretix.base.signals import logentry_display, register_payment_providers


@receiver(register_payment_providers, dispatch_uid="payment_icepay")
def register_payment_provider(sender, **kwargs):
    from .payment import Icepay
    return Icepay


@receiver(signal=logentry_display, dispatch_uid="icepay_logentry_display")
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type != 'pretix_icepay.event':
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
        return _('ICEPAY reported an event: {}').format(text)
