from importlib import import_module

from django.utils.encoding import force_text
from django.http import QueryDict
from django.core.urlresolvers import get_callable

from .models import LoggedRequest
from .utils import get_client_ip
from .exception import ThrottlingException
from .config import DEFAULT_THROTTLING_VALIDATORS, THROTTLING_FAILURE_VIEW
from django.template.defaultfilters import truncatechars


class SecurityData(object):

    def __init__(self, type, message=None, hidden_data=('password',)):
        self.type = type
        self.message = message or ''
        self.hidden_data = hidden_data


class LogMiddleware(object):

    def _render_throttling(self, request, exception):
        return get_callable(THROTTLING_FAILURE_VIEW)(request, exception)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Check if throttling is not exempted
        if not getattr(callback, 'throttling_exempt', False):
            try:
                for validator in import_module(DEFAULT_THROTTLING_VALIDATORS).validators:
                    validator.validate(request)
            except ThrottlingException as ex:
                request._security_data = SecurityData(LoggedRequest.THROTTLED_REQUEST, force_text(ex))
                return self._render_throttling(request, ThrottlingException('ted'))

    def process_response(self, request, response):
        user = hasattr(request, 'user') and request.user.is_authenticated() and request.user or None
        status = LoggedRequest.FINE
        if response.status_code >= 500:
            status = LoggedRequest.ERROR
        elif response.status_code >= 400:
            status = LoggedRequest.WARNING

        get_params = isinstance(request.GET, QueryDict) and request.GET.dict() or request.GET
        post_params = isinstance(request.POST, QueryDict) and request.POST.dict() or request.POST
        security_data = getattr(request, '_security_data', SecurityData(LoggedRequest.COMMON_REQUEST))

        for hidden in security_data.hidden_data:
            if hidden in post_params:
                del post_params[hidden]

        LoggedRequest.objects.create(status=status, path=truncatechars(request.path, 250),
                                     response_code=response.status_code, user=user, ip=get_client_ip(request),
                                     get_params=get_params, post_params=post_params,
                                     method=request.method.upper(), type=security_data.type,
                                     error_description=security_data.message)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ThrottlingException):
            request._security_data = SecurityData(LoggedRequest.THROTTLED_REQUEST, force_text(exception))
            return self._render_throttling(request, exception)
