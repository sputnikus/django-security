from __future__ import unicode_literals

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.template.defaultfilters import truncatechars
from django.utils.encoding import force_text, python_2_unicode_compatible

from json_field.fields import JSONField

from ipware.ip import get_ip

from security.config import LOG_REQUEST_BODY_LENGTH, LOG_RESPONSE_BODY_LENGTH, LOG_RESPONSE_BODY_CONTENT_TYPES
from security.utils import get_headers


# Prior to Django 1.5, the AUTH_USER_MODEL setting does not exist.
AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class LoggedRequestManager(models.Manager):
    """
    Create new LoggedRequest instance from HTTP request
    """

    def prepare_from_request(self, request):
        user = hasattr(request, 'user') and request.user.is_authenticated() and request.user or None
        path = truncatechars(request.path, 200)
        request_body = truncatechars(force_text(request.body[:LOG_REQUEST_BODY_LENGTH + 1],
                                     errors='replace'), LOG_REQUEST_BODY_LENGTH)

        return self.model(headers=get_headers(request), request_body=request_body, user=user,
                          method=request.method.upper(),
                          path=path, queries=request.GET.dict(), is_secure=request.is_secure(),
                          ip=get_ip(request), request_timestamp=timezone.now())


@python_2_unicode_compatible
class LoggedRequest(models.Model):

    FINE = 1
    WARNING = 2
    ERROR = 3

    STATUS_CHOICES = (
        (FINE, _('Fine')),
        (WARNING, _('Warning')),
        (ERROR, _('Error'))
    )

    COMMON_REQUEST = 1
    THROTTLED_REQUEST = 2
    SUCCESSFUL_LOGIN_REQUEST = 3
    UNSUCCESSFUL_LOGIN_REQUEST = 4

    TYPE_CHOICES = (
        (COMMON_REQUEST, _('Common request')),
        (THROTTLED_REQUEST, _('Throttled request')),
        (SUCCESSFUL_LOGIN_REQUEST, _('Successful login request')),
        (UNSUCCESSFUL_LOGIN_REQUEST, _('Unsuccessful login request'))
    )

    objects = LoggedRequestManager()

    # Request information
    request_timestamp = models.DateTimeField(_('Request timestamp'), null=False, blank=False, db_index=True)
    method = models.CharField(_('Method'), max_length=7, null=False, blank=False)
    path = models.CharField(_('URL path'), max_length=255, null=False, blank=False)
    queries = JSONField(_('Queries'), null=True, blank=True)
    headers = JSONField(_('Headers'), null=True, blank=True)
    request_body = models.TextField(_('Request body'), null=False, blank=True)
    is_secure = models.BooleanField(_('HTTPS connection'), default=False, null=False, blank=False)

    # Response information
    response_timestamp = models.DateTimeField(_('Response timestamp'), null=False, blank=False)
    response_code = models.PositiveSmallIntegerField(_('Response code'), null=False, blank=False)
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS_CHOICES, null=False, blank=False)
    type = models.PositiveSmallIntegerField(_('Request type'), choices=TYPE_CHOICES, default=COMMON_REQUEST, null=False,
                                            blank=False)
    response_body = models.TextField(_('Response body'), null=False, blank=True)
    error_description = models.TextField(_('Error description'), null=True, blank=True)

    # User information
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    ip = models.GenericIPAddressField(_('IP address'), null=False, blank=False)

    def get_status(self, response):
        if response.status_code >= 500:
            return LoggedRequest.ERROR
        elif response.status_code >= 400:
            return LoggedRequest.WARNING
        else:
            return LoggedRequest.FINE

    def update_from_response(self, response):
        self.response_timestamp = timezone.now()
        self.status = self.get_status(response)
        self.response_code = response.status_code

        if not response.streaming and response.get('content-type', '').split(';')[0] in LOG_RESPONSE_BODY_CONTENT_TYPES:
            response_body = truncatechars(force_text(response.content[:LOG_RESPONSE_BODY_LENGTH + 1],
                                                     errors='replace'), LOG_RESPONSE_BODY_LENGTH)
        else:
            response_body = ''

        self.response_body = response_body

    def response_time(self):
        return '%s ms' % ((self.response_timestamp - self.request_timestamp).microseconds / 1000)
    response_time.short_description = _('Response time')

    def short_path(self):
        return truncatechars(self.path, 20)
    short_path.short_description = _('Path')
    short_path.filter_by = 'path'
    short_path.order_by = 'path'

    def __str__(self):
        return self.path

    class Meta:
        ordering = ('-request_timestamp',)
        verbose_name = _('Logged request')
        verbose_name_plural = _('Logged requests')
