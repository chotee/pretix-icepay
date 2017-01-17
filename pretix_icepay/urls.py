from django.conf.urls import (
    include,
    url)

from .views import (
    failure,
    success,
    webhook)

event_patterns = [
    url(r'^icepay/', include([
        url(r'^failure/$', failure, name='failure'),
        url(r'^success/$', success, name='success'),
        url(r'^webhook/$', webhook, name='webhook'),
    ])),
]
