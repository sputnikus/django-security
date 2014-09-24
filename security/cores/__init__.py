from __future__ import unicode_literals

from is_core.main import UIRestModelISCore
from django.utils.translation import ugettext_lazy as _

from security.models import LoggedRequest


class RequestsLogIsCore(UIRestModelISCore):
    model = LoggedRequest
    list_display = ('request_timestamp', 'response_timestamp', 'has_response', 'status', 'response_code', 'short_path', 'ip',
                    'user', 'method', 'type')

    form_request_fieldset = (_('Request'), {'fields': ('request_timestamp', 'method', 'path', 'queries', 'headers',
                                                       'body', 'is_secure')})
    form_response_fieldset = (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'type',
                                                         'error_description', 'has_response')})
    form_user_information_fieldset = (_('User information'), {'fields': ('user', 'ip')})
    form_extra_information_fieldset = (_('Extra information'), {'fields': ('response_time',)})
    abstract = True

    def get_form_fieldsets(self, request, obj=None):
        if obj and obj.has_response:
            return (self.form_request_fieldset, self.form_response_fieldset, self.form_user_information_fieldset,
                    self.form_extra_information_fieldset)
        return (self.form_request_fieldset, self.form_user_information_fieldset)

    def has_create_permission(self, request, obj=None):
        return False

    def has_update_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
