from django.contrib import admin

from apps.test_security.views import (
    extra_throttling_view, hide_request_body_view, log_exempt_view, proxy_view, throttling_exempt_view
)

try:
    from django.conf.urls import url
except ImportError:
    from django.urls import re_path as url


urlpatterns = [
    url('admin/', admin.site.urls),
    url('proxy/', proxy_view),
    url('hide-request-body/', hide_request_body_view),
    url('log-exempt/', log_exempt_view),
    url('throttling-exempt/', throttling_exempt_view),
    url('extra-throttling/', extra_throttling_view),
]
