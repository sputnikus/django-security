from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from is_core.generic_views.inlines.inline_form_views import TabularInlineFormView

from security.cores import RequestsLogIsCore as OriginRequestsLogIsCore
from security.reversion_log.models import RequestRevision


class RequestRevisionTabularInlineFormView(TabularInlineFormView):
    model = RequestRevision


class RequestsLogIsCore(OriginRequestsLogIsCore):
    form_fieldsets = (
        (_('Request'), {'fields': ('request_timestamp', 'method', 'path', 'queries', 'headers', 'request_body',
                                   'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_body', 'type',
                                    'error_description')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('response_time',)}),
        (_('Revisions'), {'inline_view': 'RequestRevisionTabularInlineFormView'})
    )
    abstract = True
    form_inline_views = [RequestRevisionTabularInlineFormView]
