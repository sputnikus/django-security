from __future__ import unicode_literals

from is_core.main import UIRestModelISCore

from security.models import LoggedRequest


class LoggedRequestIsCore(UIRestModelISCore):
    model = LoggedRequest
    list_display = ('timestamp', 'status', 'response_code', 'path', 'ip', 'user')
