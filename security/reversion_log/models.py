from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible

from reversion.models import Revision
from security.models import LoggedRequest


@python_2_unicode_compatible
class RequestRevision(models.Model):

    logged_request = models.ForeignKey(LoggedRequest, verbose_name=_('logged request'), null=False, blank=False)
    revision = models.OneToOneField(Revision, verbose_name=_('revision'), null=False, blank=False)

    def __str__(self):
        return ' #%s' % self.pk

    class Meta:
        verbose_name = _('Logged request revision')
        verbose_name_plural = _('Logged requests revisions')
