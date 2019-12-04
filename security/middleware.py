import traceback

from ipware.ip import get_ip

from django import http
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.db.transaction import get_connection
from django.urls import is_valid_path, get_callable

from .config import settings
from .exception import ThrottlingException
from .models import InputLoggedRequest, InputLoggedRequestType
from .utils import get_throttling_validators, get_view_from_request_or_none

try:
    from importlib import import_module
except ImportError:  # For Django < 1.8
    from django.utils.importlib import import_module



if 'security.contrib.reversion_log' in django_settings.INSTALLED_APPS:
    if 'reversion' not in django_settings.INSTALLED_APPS:
        raise ImproperlyConfigured('For reversion log is necessary install "django-reversion"')

    # Supports two version of reversion library
    try:
        from reversion.signals import post_revision_commit

        def create_revision_request_log(sender, revision, versions, **kwargs):
            from security.contrib.reversion_log.models import InputRequestRevision

            connection = get_connection()
            if getattr(connection, 'input_logged_request', False):
                InputRequestRevision.objects.create(logged_request=connection.input_logged_request, revision=revision)

        post_revision_commit.connect(create_revision_request_log)
    except ImportError:
        pass


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
        connection = get_connection()

        view = get_view_from_request_or_none(request)
        if (get_ip(request) not in settings.LOG_REQUEST_IGNORE_IP
               and request.path not in settings.LOG_REQUEST_IGNORE_URL_PATHS
               and not getattr(view, 'log_exempt', False)):
            input_logged_request = InputLoggedRequest.objects.prepare_from_request(request)
            if getattr(view, 'hide_request_body', False):
                input_logged_request.request_body = ''
            input_logged_request.save()
            request.input_logged_request = input_logged_request
            connection.input_logged_request = input_logged_request

        output_logged_requests = getattr(connection, 'output_logged_requests', [])
        output_logged_requests.append([])
        request.output_logged_requests = output_logged_requests
        connection.output_logged_requests = output_logged_requests

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

        output_logged_requests = (
            request.output_logged_requests.pop() if hasattr(request, 'output_logged_requests') else ()
        )
        [logged_request.create(input_logged_request) for logged_request in output_logged_requests]
        return response

    def process_exception(self, request, exception):
        if hasattr(request, 'input_logged_request'):
            logged_request = request.input_logged_request
            logged_request.error_description = traceback.format_exc()
            logged_request.exception_name = exception.__class__.__name__
            if isinstance(exception, ThrottlingException):
                logged_request.type = InputLoggedRequestType.THROTTLED_REQUEST
                return self._render_throttling(request, exception)
