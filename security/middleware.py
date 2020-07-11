import traceback

from django import http
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import is_valid_path, get_callable

from .compatibility import get_client_ip
from .config import settings
from .exception import ThrottlingException
from .models import InputLoggedRequest, InputLoggedRequestType
from .utils import (
    get_throttling_validators, get_view_from_request_or_none, log_context_manager
)

from importlib import import_module


class LogMiddleware:

    response_redirect_class = http.HttpResponsePermanentRedirect

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        response = self.process_request(request)
        response = response or self.get_response(request)
        response = self.process_response(request, response)
        return response

    def process_request(self, request):
        view = get_view_from_request_or_none(request)
        input_logged_request = None
        if (get_client_ip(request)[0] not in settings.LOG_REQUEST_IGNORE_IP
               and request.path not in settings.LOG_REQUEST_IGNORE_URL_PATHS
               and not getattr(view, 'log_exempt', False)):
            input_logged_request = InputLoggedRequest.objects.prepare_from_request(request)
            if getattr(view, 'hide_request_body', False):
                input_logged_request.request_body = ''
            input_logged_request.save()
            request.input_logged_request = input_logged_request

        log_context_manager.start(input_logged_request=input_logged_request)

        # Return a redirect if necessary
        if self.should_redirect_with_slash(request):
            return self.response_redirect_class(self.get_full_path_with_slash(request))

    def get_full_path_with_slash(self, request):
        """
        Return the full path of the request with a trailing slash appended.

        Raise a RuntimeError if settings.DEBUG is True and request.method is
        POST, PUT, or PATCH.
        """
        new_path = request.get_full_path(force_append_slash=True)
        if django_settings.DEBUG and request.method in {'POST', 'PUT', 'PATCH'}:
            raise RuntimeError(
                "You called this URL via %(method)s, but the URL doesn't end "
                "in a slash and you have SECURITY_APPEND_SLASH set. Django can't "
                "redirect to the slash URL while maintaining %(method)s data. "
                "Change your form to point to %(url)s (note the trailing "
                "slash), or set SECURITY_APPEND_SLASH=False in your Django settings." % {
                    'method': request.method,
                    'url': request.get_host() + new_path,
                }
            )
        return new_path

    def should_redirect_with_slash(self, request):
        """
        Return True if settings.APPEND_SLASH is True and appending a slash to
        the request path turns an invalid path into a valid one.
        """
        if settings.APPEND_SLASH and not request.get_full_path().endswith('/'):
            urlconf = getattr(request, 'urlconf', None)
            return (
                not is_valid_path(request.path_info, urlconf) and
                is_valid_path('{}/'.format(request.path_info), urlconf)
            )
        return False

    def _render_throttling(self, request, exception):
        return get_callable(settings.THROTTLING_FAILURE_VIEW)(request, exception)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        if getattr(request, 'input_logged_request', False):

            throttling_validators = getattr(callback, 'throttling_validators', None)
            if throttling_validators is None:
                throttling_validators = get_throttling_validators('default_validators')

            try:
                for validator in throttling_validators:
                    validator.validate(request)
            except ThrottlingException as exception:
                return self.process_exception(request, exception)

    def process_response(self, request, response):
        input_logged_request = getattr(request, 'input_logged_request', None)
        if input_logged_request:
            input_logged_request.update_from_response(response)
            input_logged_request.save()

        log_context_manager.end()
        return response

    def process_exception(self, request, exception):
        if hasattr(request, 'input_logged_request'):

            logged_request = request.input_logged_request
            if isinstance(exception, ThrottlingException):
                logged_request.type = InputLoggedRequestType.THROTTLED_REQUEST
                return self._render_throttling(request, exception)
            else:
                logged_request.error_description = traceback.format_exc()
                logged_request.exception_name = exception.__class__.__name__
