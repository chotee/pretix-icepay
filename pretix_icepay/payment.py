import json
import logging
import operator
from collections import OrderedDict

from icepay import IcepayClient

from django import forms
from django.contrib import messages
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from pretix.base.payment import BasePaymentProvider
from pretix.multidomain.urlreverse import build_absolute_uri
from requests import HTTPError

logger = logging.getLogger('pretix_icepay')

IDEAL_BANKS = {  # Code : Display name
    'ABNAMRO': 'ABN AMRO',
    'ASNBANK': 'ASN Bank',
    'BUNQ': 'Bunq',
    'ING': 'ING',
    'KNAB': 'Knab',
    'RABOBANK': 'Rabobank',
    'SNSBANK': 'SNS Bank',
    'SNSREGIOBANK': 'RegioBank',
    'TRIODOSBANK': 'Triodos Bank',
    'VANLANSCHOT': 'van Lanshot'
}


class Icepay(BasePaymentProvider):
    identifier = 'icepay'
    verbose_name = _('Ideal via icepay')

    @property
    def settings_form_fields(self):
        return OrderedDict(
            list(super().settings_form_fields.items()) + [
                ('merchant_id', forms.CharField(label=_('Merchant ID'))),
                ('secret_code', forms.CharField(label=_('Secret code')))
            ]
        )

    @property
    def payment_form_fields(self):
        bank_choices = sorted(IDEAL_BANKS.items(), key=operator.itemgetter(1))
        bank_choices.insert(0, (None, _('Your bank')))
        return {
            'issuer': forms.ChoiceField(
                required=True, label=_('Ideal bank'), choices=bank_choices)}

    def payment_is_valid_session(self, request):
        return True

    def order_prepare(self, request, order):
        return self.checkout_prepare(request, None)

    def checkout_confirm_render(self, request) -> str:
        template = get_template('icepay/checkout_payment_confirm.html')
        ctx = {
            'bank_name': IDEAL_BANKS[request.session['payment_icepay_issuer']],
            'request': request,
            'event': self.event,
            'settings': self.settings}
        return template.render(ctx)

    def order_can_retry(self, order):
        return True

    def get_client(self):
        """Returns an IcepayClient configured with the event's credentials."""
        return IcepayClient(
            self.settings.get('merchant_id'),
            self.settings.get('secret_code'))

    def payment_perform(self, request, order) -> str:
        client = self.get_client()

        # Retrieve and increment attempt count to guarantee unique OrderID.
        if order.payment_info is not None:
            payment_info = json.loads(order.payment_info)
            payment_info.setdefault('icepay_attempt', 0)
            payment_info['icepay_attempt'] += 1
        else:
            payment_info = {'icepay_attempt': 1}
        order.payment_info = json.dumps(payment_info)
        order.save()

        checkout_params = {
            'Amount': int(order.total * 100),
            'Country': 'NL',
            'Currency': self.event.currency.upper(),
            'Description': str(self.event.name),
            'EndUserIP': request.META.get(
                'HTTP_X_FORWARDED_FOR', request.META['REMOTE_ADDR']),
            'Issuer': request.session['payment_icepay_issuer'],
            'Language': request.LANGUAGE_CODE.split('-')[0].upper(),
            'OrderID': '{}-{}'.format(
                order.id, payment_info['icepay_attempt']),
            'Reference': str(order.code),
            'PaymentMethod': 'IDEAL',
            'URLCompleted': build_absolute_uri(
                request.event, 'plugins:pretix_icepay:success'),
            'URLError': build_absolute_uri(
                request.event, 'plugins:pretix_icepay:failure')}
        try:
            response = client.Checkout(checkout_params)
        except HTTPError as e:
            messages.error(request, _(
                'We had trouble communicating with ICEPAY. Please try again '
                'and contact support if the problem persists.'))
            logger.error('ICEPAY Error: %s', str(e.response.text))
        else:
            return response['PaymentScreenURL']

    def order_pending_render(self, request, order) -> str:
        template = get_template('icepay/pending.html')
        return template.render()
