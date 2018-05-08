from django.db import models
from django.utils.translation import ugettext_lazy as _

from reversion.models import Revision

from security.models import InputLoggedRequest


class InputRequestRevision(models.Model):

    logged_request = models.ForeignKey(InputLoggedRequest, verbose_name=_('logged request'), null=False, blank=False,
                                       on_delete=models.CASCADE, related_name='input_logged_request_revisions')
    revision = models.OneToOneField(Revision, verbose_name=_('revision'), null=False, blank=False,
                                    on_delete=models.CASCADE, related_name='input_logged_request_revision')

    def __str__(self):
        return ' #%s' % self.pk

    class Meta:
        verbose_name = _('Logged request revision')
        verbose_name_plural = _('Logged requests revisions')
