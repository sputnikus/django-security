from django.http import HttpResponse

from security.throttling import PerRequestThrottlingValidator
from security.decorators import hide_request_body, log_exempt, throttling_exempt, throttling
from security.transport import security_requests as requests


def proxy_view(request):
    return HttpResponse(
        requests.get(
            request.GET.get('url'),
            slug='proxy',
            related_objects=(request.user,) if request.user.is_authenticated else ()
        ).content
    )


@hide_request_body()
def hide_request_body_view(request):
    return HttpResponse()


@log_exempt()
def log_exempt_view(request):
    return HttpResponse()


@throttling_exempt()
def throttling_exempt_view(request):
    return HttpResponse()


@throttling(PerRequestThrottlingValidator(60, 1))
def extra_throttling_view(request):
    return HttpResponse()
