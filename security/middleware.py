from importlib import import_module

from django.utils.encoding import force_text
from django.core.urlresolvers import get_callable

from .models import LoggedRequest
from .exception import ThrottlingException
from .config import DEFAULT_THROTTLING_VALIDATORS, THROTTLING_FAILURE_VIEW


class LogMiddleware(object):

    def process_request(self, request):
        request._logged_request = LoggedRequest.objects.prepare_from_request(request)

    def _render_throttling(self, request, exception):
        return get_callable(THROTTLING_FAILURE_VIEW)(request, exception)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Exempt all log
        if getattr(request, '_logged_request', False):

            if getattr(callback, 'log_exempt', False):
                del request._logged_request

            # TODO: this is not the best solution if the request throw exception inside process_request of some Middleware
            # the bode will be included (But I didn't have better solution now)
            if getattr(callback, 'hide_request_body', False):
                request._logged_request.body = ''

            # Check if throttling is not exempted
            if not getattr(callback, 'throttling_exempt', False):
                try:
                    for validator in import_module(DEFAULT_THROTTLING_VALIDATORS).validators:
                        validator.validate(request)
                except ThrottlingException as exception:
                    return self.process_exception(request, exception)

    def process_response(self, request, response):
        if hasattr(request, '_logged_request'):
            request._logged_request.update_from_response(response)
            request._logged_request.save()
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ThrottlingException) and hasattr(request, '_logged_request'):
            logged_request = request._logged_request
            logged_request.type = LoggedRequest.THROTTLED_REQUEST
            logged_request.error_description = force_text(exception)
            return self._render_throttling(request, exception)
