import json
import logging

import stripe
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pretix.base.models import Order, Quota
from pretix.base.services.orders import mark_order_paid, mark_order_refunded
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.utils import event_view
from pretix_icepay.payment import Icepay

logger = logging.getLogger('pretix_icepay')


@event_view(require_live=False)
def result(request, *args, **kwargs):
    """Handle ICEPAY result after the user comes back from the payment page."""
    provider = Icepay(request.event)
    client = provider.get_client()
    try:
        client.validate_postback(request.GET)
    except AssertionError:
        logger.error('Invalid checksum on postback: %s', request.META['QUERY_STRING'])
        messages.error(request, _('It looks like something went wrong with your payment'))
        return redirect(eventreverse(request.event, 'presale:event.index'))

    # Valid postback, and thus ICEPAY response:
    status = request.GET.get('Status')
    order = Order.objects.get(code=request.GET['Reference'])
    if status == 'OK':
        try:
            mark_order_paid(order, 'icepay')
        except Quota.QuotaExceededException as e:
            messages.error(request, str(e))
        else:
            view_params = {'order': order.code, 'secret': order.secret}
            order_url = eventreverse(
                request.event, 'presale:event.order', kwargs=view_params)
            return redirect(order_url + '?paid=yes')
    else:
        messages.error(request, _(
            'It looks like something went wrong with your payment'))
        return redirect(eventreverse(
            request.event, 'presale:event.order', kwargs={
                'order': order.code, 'secret': order.secret}))


@csrf_exempt
@require_POST
@event_view(require_live=False)
def webhook(request, *args, **kwargs):
    event_json = json.loads(request.body.decode('utf-8'))

    # We do not check for the event type as we are not interested in the event it self,
    # we just use it as a trigger to look the charge up to be absolutely sure.
    # Another reason for this is that stripe events are not authenticated, so they could
    # come from anywhere.

    if event_json['data']['object']['object'] == "charge":
        charge_id = event_json['data']['object']['id']
    elif event_json['data']['object']['object'] == "dispute":
        charge_id = event_json['data']['object']['charge']
    else:
        return HttpResponse("Not interested in this data type", status=200)

    prov = Icepay(request.event)
    prov._init_api()
    try:
        charge = stripe.Charge.retrieve(charge_id)
    except stripe.error.StripeError:
        logger.exception('Stripe error on webhook. Event data: %s' % str(event_json))
        return HttpResponse('Charge not found', status=500)

    metadata = charge['metadata']
    if 'event' not in metadata:
        return HttpResponse('Event not given in charge metadata', status=200)

    if int(metadata['event']) != request.event.pk:
        return HttpResponse('Not interested in this event', status=200)

    try:
        order = request.event.orders.get(id=metadata['order'])
    except Order.DoesNotExist:
        return HttpResponse('Order not found', status=200)

    order.log_action('pretix_icepay.event', data=event_json)

    if order.status == Order.STATUS_PAID and (charge['refunds']['total_count'] or charge['dispute']):
        mark_order_refunded(order, user=None)

    return HttpResponse(status=200)
