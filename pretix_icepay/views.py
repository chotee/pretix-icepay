import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pretix.base.models import Order, Quota
from pretix.base.services.orders import mark_order_paid
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.utils import event_view
from pretix_icepay.payment import Icepay

logger = logging.getLogger('pretix_icepay')


@event_view(require_live=False)
def failure(request, *args, **kwargs):
    """Handle failed return from ICEPAY payment screen."""
    messages.error(request, _(
        'It looks like something went wrong with your payment'))
    # Don't send user to order page if ICEPAY checksum is bad
    if not valid_icepay_postback(request):
        return redirect(eventreverse(request.event, 'presale:event.index'))

    # Load order and redirect user to payment page again
    order = Order.objects.get(code=request.GET['Reference'])
    return redirect(eventreverse(
        request.event, 'presale:event.order', kwargs={
            'order': order.code, 'secret': order.secret}))


@event_view(require_live=False)
def success(request, *args, **kwargs):
    """Handle successful return from ICEPAY payment screen."""
    if not valid_icepay_postback(request):
        messages.error(request, _(
            'It looks like something went wrong with your payment'))
        return redirect(eventreverse(request.event, 'presale:event.index'))

    # Valid postback, and thus ICEPAY response:
    order = Order.objects.get(code=request.GET['Reference'])
    try:
        mark_order_paid(order, 'icepay')
    except Quota.QuotaExceededException as e:
        # User is fucked.. what do?
        messages.error(request, str(e))
    else:
        view_params = {'order': order.code, 'secret': order.secret}
        order_url = eventreverse(
            request.event, 'presale:event.order', kwargs=view_params)
        return redirect(order_url + '?paid=yes')


@csrf_exempt
@event_view(require_live=False)
def webhook(request, *args, **kwargs):
    """Handle ICEPAY postbacks to update order payment status."""
    if valid_icepay_postback(request) and request.POST.get('Status') == 'OK':
        order = Order.objects.get(code=request.POST['Reference'])
        try:
            mark_order_paid(order, 'icepay')
        except Quota.QuotaExceededException:
            logger.exception(
                'Out of tickets in response to ICEPAY order %s', order.code)
    return HttpResponse(status=200)


def valid_icepay_postback(request):
    """Returns whether or not the checksum of ICEPAY parameters is correct."""
    provider = Icepay(request.event)
    client = provider.get_client()
    if request.method not in {'GET', 'POST'}:
        return False
    try:
        parameters = getattr(request, request.method)
        client.validate_postback(parameters)
        return True
    except AssertionError:
        logger.error('ICEPAY: Bad checksum on postback: %r', parameters)
    return False
