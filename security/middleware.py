from django.utils.encoding import force_text
from django.http import HttpResponse, QueryDict
from django.shortcuts import render_to_response

from .models import LoggedRequest
from .utils import get_client_ip
from .exception import ThrottlingException
from .config import DEFAULT_THROTTLING_VALIDATORS
from django.template.context import RequestContext


class LogMiddleware(object):

    def _render_throttling(self, request):
        response = render_to_response('429.html', context_instance=RequestContext(request))
        response.status_code = 429
        return response

    def process_request(self, request):
        try:
            for validator in DEFAULT_THROTTLING_VALIDATORS:
                validator.validate(request)
        except ThrottlingException:
            return self._render_throttling(request)

    def process_response(self, request, response):
        user = request.user.is_authenticated() and request.user or None
        status = LoggedRequest.FINE
        if response.status_code >= 500:
            status = LoggedRequest.ERROR
        elif response.status_code >= 400:
            status = LoggedRequest.WARNING

        get_params = isinstance(request.GET, QueryDict) and request.GET.dict() or request.GET
        post_params = isinstance(request.POST, QueryDict) and request.POST.dict() or request.POST

        LoggedRequest.objects.create(status=status, path=request.path,
                                     response_code=response.status_code, user=user, ip=get_client_ip(request),
                                     get_params=get_params, post_params=post_params)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ThrottlingException):
            return self._render_throttling(request)