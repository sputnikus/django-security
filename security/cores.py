from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from is_core.main import UIRESTModelISCore

from security.models import LoggedRequest


class RequestsLogIsCore(UIRESTModelISCore):
    model = LoggedRequest
    list_display = (
        'request_timestamp', 'response_timestamp', 'status', 'response_code', 'short_path', 'ip',
        'user', 'method', 'type'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('request_timestamp', 'method', 'path', 'queries', 'headers', 'request_body',
                                   'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_body', 'type',
                                    'error_description')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('response_time',)})
    )

    abstract = True

    def has_create_permission(self, request, obj=None):
        return False

    def has_update_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
