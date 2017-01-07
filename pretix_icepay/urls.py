from django.conf.urls import (
    include,
    url)

from .views import (
    result,
    webhook)

event_patterns = [
    url(r'^icepay/', include([
        url(r'^result/$', result, name='result'),
        url(r'^webhook/$', webhook, name='webhook'),
    ])),
]
