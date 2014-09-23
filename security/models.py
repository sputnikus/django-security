from __future__ import unicode_literals

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.template.defaultfilters import truncatechars

from json_field.fields import JSONField

from security.utils import get_client_ip, get_headers


# Prior to Django 1.5, the AUTH_USER_MODEL setting does not exist.
AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class LoggedRequestManager(models.Manager):
    """
    Create new LoggedRequest instance from HTTP request
    """

    def create_from_request(self, request):
        user = hasattr(request, 'user') and request.user.is_authenticated() and request.user or None
        path = truncatechars(request.path, 200)
        body = truncatechars(request.body, 500)

        return self.create(headers=get_headers(request), body=body, user=user, method=request.method.upper(),
                           path=path, queries=request.GET.dict(), is_secure=request.is_secure(),
                           ip=get_client_ip(request))


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
    request_timestamp = models.DateTimeField(_('Timestamp'), null=False, blank=False, auto_now_add=True)
    method = models.CharField(_('Method'), max_length=7, null=False, blank=False)
    path = models.CharField(_('URL path'), max_length=255, null=False, blank=False)
    queries = JSONField(_('Queries'), null=True, blank=True)
    headers = JSONField(_('Headers'), null=True, blank=True)
    body = models.TextField(_('Body'), null=False, blank=True)
    is_secure = models.BooleanField(_('is secure'), default=False)

    # Response information
    response_timestamp = models.DateTimeField(_('Timestamp'), null=True, blank=True)
    response_code = models.PositiveSmallIntegerField(_('Response code'), null=True, blank=True)
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS_CHOICES, null=True, blank=True)
    type = models.PositiveSmallIntegerField(_('Request type'), choices=TYPE_CHOICES, default=COMMON_REQUEST, null=True,
                                            blank=True)
    error_description = models.CharField(_('Error description'), max_length=255, null=True, blank=True)

    # User information
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    ip = models.IPAddressField(_('IP address'), null=False, blank=False)

    # Log information
    # TODO: is nessesary to relate thread with request.
    # log = models.TextField(_('Log'), null=True, blank=True)

    def __unicode__(self):
        return self.path

    def save(self, *args, **kwargs):
        from security import config

        LoggedRequest.objects.filter(pk__in=LoggedRequest.objects.all()
                                     .order_by('-request_timestamp')[config.MAX_LOGGED_REQUESTS - 1:]).delete()
        super(LoggedRequest, self).save(*args, **kwargs)

    def get_status(self, response):
        if response.status_code >= 500:
            return LoggedRequest.ERROR
        elif response.status_code >= 400:
            return LoggedRequest.WARNING
        else:
            return LoggedRequest.FINE

    def update_from_response(self, response, status=None, type=None, error_description=None):
        self.request_timestamp = timezone.now()
        self.status = status or self.get_status(response)
        self.response_code = response.status_code
        if type is not None:
            self.type = type
        if error_description is not None:
            self.error_description = error_description
        self.save()

    class Meta:
        ordering = ('-request_timestamp',)
        verbose_name = _('Logged request')
        verbose_name_plural = _('Logged requests')
