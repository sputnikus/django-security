from django.contrib import admin
from django.urls import path

from apps.test_security.views import (
    proxy_view, hide_request_body_view, log_exempt_view, throttling_exempt_view, extra_throttling_view
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('proxy/', proxy_view),
    path('hide-request-body/', hide_request_body_view),
    path('log-exempt/', log_exempt_view),
    path('throttling-exempt/', throttling_exempt_view),
    path('extra-throttling/', extra_throttling_view),
]
