from __future__ import unicode_literals

from is_core.main import UIRestModelISCore

from security.models import LoggedRequest


class RequestsLogIsCore(UIRestModelISCore):
    model = LoggedRequest
    list_display = ('timestamp', 'status', 'response_code', 'ip', 'user', 'method', 'type', 'short_path')
    abstract = True

    def has_create_permission(self, request, obj=None):
        return False

    def has_update_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
