from __future__ import unicode_literals

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from json_field.fields import JSONField


# Prior to Django 1.5, the AUTH_USER_MODEL setting does not exist.
AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class LoggedRequest(models.Model):

    FINE = 1
    WARNING = 2
    ERROR = 3

    STATUS_CHOICES = (
        (FINE, _('Fine')),
        (WARNING, _('Warning')),
        (ERROR, _('Error'))
    )

    timestamp = models.DateTimeField(_('Timestamp'), null=False, blank=False, auto_now_add=True)
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS_CHOICES, null=False, blank=False)
    path = models.CharField(_('URL path'), max_length=255, null=False, blank=False)
    get_params = JSONField(_('GET params'), null=True, blank=True)
    post_params = JSONField(_('POST params'), null=True, blank=True)
    response_code = models.PositiveSmallIntegerField(_('Response code'), null=False, blank=False)
    user = models.ForeignKey(AUTH_USER_MODEL, null=True, blank=True)
    error_description = models.CharField(_('Error description'), max_length=255, null=True, blank=True)
    ip = models.IPAddressField(_('IP address'), null=False, blank=False)

    def __unicode__(self):
        return self.path

    class Meta:
        ordering = ('-timestamp',)
