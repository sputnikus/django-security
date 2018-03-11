from django.utils.translation import ugettext_lazy as _

from is_core.generic_views.inlines.inline_form_views import TabularInlineFormView

from security.cores import InputRequestsLogISCore as OriginInputRequestsLogISCore
from security.reversion_log.models import InputRequestRevision


class RequestRevisionTabularInlineFormView(TabularInlineFormView):

    model = InputRequestRevision


class InputRequestsLogISCore(OriginInputRequestsLogISCore):

    form_fieldsets = (
        (_('Request'), {'fields': ('request_timestamp', 'method', 'path', 'queries', 'request_headers_code',
                                   'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_headers_code',
                                    'response_body_code', 'type', 'error_description_code')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('response_time', 'output_logged_requests',)}),
        (_('Revisions'), {'inline_view': RequestRevisionTabularInlineFormView}),
    )
    abstract = True
