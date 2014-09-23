from importlib import import_module

from django.utils.encoding import force_text
from django.core.urlresolvers import get_callable

from .models import LoggedRequest
from .exception import ThrottlingException
from .config import DEFAULT_THROTTLING_VALIDATORS, THROTTLING_FAILURE_VIEW


class LogMiddleware(object):

    def process_request(self, request):
        print 'teeeeeeeeeed'
        request._logged_request = LoggedRequest.objects.create_from_request(request)
        print request._logged_request

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
                return self._render_throttling(request, ex)

    def process_response(self, request, response):
        if hasattr(request, '_logged_request'):
            request._logged_request.update_from_response(response)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ThrottlingException):
            logged_request = request._logged_request
            logged_request.type = LoggedRequest.THROTTLED_REQUEST
            logged_request.error_description = force_text(exception)
            logged_request.save()
            return self._render_throttling(request, exception)
