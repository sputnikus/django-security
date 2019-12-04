from django.db import models
from django.utils.translation import ugettext_lazy as _

from security.models import InputLoggedRequest


class DebugToolbarData(models.Model):

    logged_request = models.OneToOneField(
        InputLoggedRequest,
        verbose_name=_('logged request'),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name='input_logged_request_toolbar'
    )
    toolbar = models.TextField(
        verbose_name=_('toolbar'),
        null=False,
        blank=False,
    )

    def __str__(self):
        return ' #%s' % self.pk

    class Meta:
        verbose_name = _('Logged request toolbar')
        verbose_name_plural = _('Logged requests toolbars')
