import json
import logging
from collections import OrderedDict

from icepay import IcepayClient

from django import forms
from django.contrib import messages
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _

from pretix.base.models import Quota
from pretix.base.payment import BasePaymentProvider
from pretix.base.services.mail import SendMailException
from pretix.base.services.orders import mark_order_paid, mark_order_refunded
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
    'SNSREGIOBANK':'RegioBank',
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
                ('merchant_id',
                 forms.CharField(
                     label=_('Merchant ID'),
                 )),
                ('secret_code',
                 forms.CharField(
                     label=_('Secret code'),
                 )),
            ]
        )

    @property
    def payment_form_fields(self):
        return {
            'issuer': forms.ChoiceField(
                required=True,
                label=_("Ideal bank"),
                choices=[(None, _('Your bank')),] + sorted(IDEAL_BANKS.items(), key=lambda e: e[1])
            )
        }

    # def settings_content_render(self, request):
    #     return "<div class='alert alert-info'>%s<br /><code>%s</code></div>" % (
    #         _('Please configure a <a href="https://dashboard.stripe.com/account/webhooks">Stripe Webhook</a> to '
    #           'the following endpoint in order to automatically cancel orders when charges are refunded externally.'),
    #         build_absolute_uri(self.event, 'plugins:pretix_icepay:webhook')
    #     )

    def payment_is_valid_session(self, request):
        # payment_icepay_bank = request.POST.get('id_payment_icepay-payment_icepay_bank', '')
        # request.session['payment_icepay_bank'] = payment_icepay_bank
        # logger.error("payment_icepay_bank %s" % repr(request.POST))
        # return request.session.get('payment_icepay_bank', '') != ''
        return True

    def order_prepare(self, request, order):
        return self.checkout_prepare(request, None)

    # def payment_form_render(self, request) -> str:
    #     ui = self.settings.get('ui', default='pretix')
    #     # if ui == 'checkout':
    #     #     template = get_template('pretixplugins/stripe/checkout_payment_form_stripe_checkout.html')
    #     # else:
    #     template = get_template('icepay/checkout_payment_form.html')
    #     ctx = {'request': request, 'event': self.event, 'settings': self.settings, 'ideal_banks': IDEAL_BANKS}
    #     return template.render(ctx)
    #
    def checkout_confirm_render(self, request) -> str:
        template = get_template('icepay/checkout_payment_confirm.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings}
        return template.render(ctx)
    #
    # def order_can_retry(self, order):
    #     return True

    def _icepay(self):
        merchant_id = self.settings.get('merchant_id')
        secret = self.settings.get('secret_code')
        client = IcepayClient(merchant_id, secret)
        return client

    def payment_perform(self, request, order) -> str:
        client = self._icepay()
        result_url = build_absolute_uri(
            request.event, 'plugins:pretix_icepay:result')
        checkout_params = {
            'Amount': int(order.total * 100),
            'Country': 'NL',
            'Currency': self.event.currency.upper(),
            'Description': str(self.event.name),
            'EndUserIP': request.META.get(
                'HTTP_X_FORWARDED_FOR', request.META['REMOTE_ADDR']),
            'Issuer': request.session['payment_icepay_issuer'],
            'Language': request.LANGUAGE_CODE.split('-')[0].upper(),
            'OrderID': str(order.id),
            'PaymentMethod': 'IDEAL',
            'URLCompleted': result_url,
            'URLError': result_url}
        try:
            response = client.Checkout(checkout_params)
        except HTTPError as e:
            messages.error(request, _(
                'We had trouble communicating with ICEPAY. Please try again '
                'and contact support if the problem persists.'))
            logger.error('ICEPAY Error: %s', str(e.response.text))
        else:
            return response['PaymentScreenURL']

    # def order_pending_render(self, request, order) -> str:
    #     if order.payment_info:
    #         payment_info = json.loads(order.payment_info)
    #     else:
    #         payment_info = None
    #     template = get_template('icepay/pending.html')
    #     ctx = {'request': request, 'event': self.event, 'settings': self.settings,
    #            'order': order, 'payment_info': payment_info}
    #     return template.render(ctx)
    #
    # def order_control_render(self, request, order) -> str:
    #     if order.payment_info:
    #         payment_info = json.loads(order.payment_info)
    #         if 'amount' in payment_info:
    #             payment_info['amount'] /= 100
    #     else:
    #         payment_info = None
    #     template = get_template('icepay/control.html')
    #     ctx = {'request': request, 'event': self.event, 'settings': self.settings,
    #            'payment_info': payment_info, 'order': order}
    #     return template.render(ctx)

    # def order_control_refund_render(self, order) -> str:
    #     return '<div class="alert alert-info">%s</div>' % _('The money will be automatically refunded.')
    #
    # def order_control_refund_perform(self, request, order) -> "bool|str":
    #     self._init_api()
    #
    #     if order.payment_info:
    #         payment_info = json.loads(order.payment_info)
    #     else:
    #         payment_info = None
    #
    #     if not payment_info:
    #         mark_order_refunded(order, user=request.user)
    #         messages.warning(request, _('We were unable to transfer the money back automatically. '
    #                                     'Please get in touch with the customer and transfer it back manually.'))
    #         return
    #
    #     try:
    #         ch = stripe.Charge.retrieve(payment_info['id'])
    #         ch.refunds.create()
    #         ch.refresh()
    #     except (stripe.error.InvalidRequestError, stripe.error.AuthenticationError, stripe.error.APIConnectionError) \
    #             as e:
    #         if e.json_body:
    #             err = e.json_body['error']
    #             logger.exception('Stripe error: %s' % str(err))
    #         else:
    #             err = {'message': str(e)}
    #             logger.exception('Stripe error: %s' % str(e))
    #         messages.error(request, _('We had trouble communicating with Stripe. Please try again and contact '
    #                                   'support if the problem persists.'))
    #         logger.error('Stripe error: %s' % str(err))
    #     except stripe.error.StripeError:
    #         mark_order_refunded(order, user=request.user)
    #         messages.warning(request, _('We were unable to transfer the money back automatically. '
    #                                     'Please get in touch with the customer and transfer it back manually.'))
    #     else:
    #         order = mark_order_refunded(order, user=request.user)
    #         order.payment_info = str(ch)
    #         order.save()
