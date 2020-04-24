import json

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.template.defaultfilters import truncatechars
from django.utils.html import format_html, format_html_join, mark_safe
from django.utils.translation import ugettext_lazy as _

from pyston.paginator import BaseOffsetPaginatorWithoutTotal
from pyston.utils.decorators import filter_by, order_by

from is_core.generic_views.inlines.inline_table_views import InlineTableView
from is_core.generic_views.mixins import TabItem, TabsViewMixin
from is_core.generic_views.table_views import TableView
from is_core.main import UIRESTModelISCore
from is_core.utils import get_obj_url
from is_core.utils.decorators import short_description

from security.config import settings
from security.models import CommandLog, InputLoggedRequest, OutputLoggedRequest, CeleryTaskLog, CeleryTaskRunLog

from ansi2html import Ansi2HTMLConverter

from .filters import CeleryTaskLogStateFilter

from django.utils.html import format_html_join


def render_model_objects_with_link(request, objs):
    return format_html_join(
        ', ',
        '<a href="{}">{}</a>',
        ((get_obj_url(request, obj), str(obj)) for obj in objs)
    )


def display_json(value):
    return json.dumps(value, indent=4, ensure_ascii=False, cls=DjangoJSONEncoder)


def display_as_code(value):
    return format_html('<code style="white-space:pre-wrap;">{}</code>', value) if value else value



class DisplayRelatedObjectsMixin:

    @short_description(_('related objects'))
    def display_related_objects(self, obj, request):
        return render_model_objects_with_link(
            request,
            [related_object.object for related_object in obj.related_objects.all() if related_object.object]
        )


class RequestsLogISCore(DisplayRelatedObjectsMixin, UIRESTModelISCore):

    abstract = True

    can_create = can_update = can_delete = False

    rest_paginator = BaseOffsetPaginatorWithoutTotal

    @short_description(_('queries'))
    def queries_code(self, obj=None):
        return display_as_code(display_json(obj.queries)) if obj else None

    @short_description(_('request body'))
    def request_body_code(self, obj=None):
        return display_as_code(obj.request_body) if obj else None

    @short_description(_('request headers'))
    def request_headers_code(self, obj=None):
        return display_as_code(display_json(obj.request_headers)) if obj else None

    @short_description(_('response body'))
    def response_body_code(self, obj=None):
        return display_as_code(obj.response_body) if obj else None

    @short_description(_('response headers'))
    def response_headers_code(self, obj=None):
        return display_as_code(display_json(obj.response_headers)) if obj else None

    @short_description(_('error description'))
    def error_description_code(self, obj=None):
        return display_as_code(obj.error_description) if obj else None


class InputRequestsLogISCore(RequestsLogISCore):

    model = InputLoggedRequest
    abstract = True

    ui_list_fields = (
        'created_at', 'changed_at', 'request_timestamp', 'response_timestamp', 'response_time', 'status',
        'response_code', 'host', 'short_path', 'slug', 'ip', 'user', 'method', 'type', 'short_response_body',
        'short_request_body', 'short_queries', 'short_request_headers'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('created_at', 'changed_at', 'request_timestamp', 'host', 'method', 'path',
                                   'queries_code', 'request_headers_code', 'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_headers_code',
                                    'response_body_code', 'type', 'error_description_code')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('slug', 'response_time', 'output_logged_requests',
                                             'display_related_objects')}),
    )

    def get_form_fieldsets(self, request, obj=None):
        form_fieldsets = list(super().get_form_fieldsets(request, obj))

        app_names = {app.name for app in apps.get_app_configs()}

        if (settings.SHOW_DEBUG_TOOLBAR and 'security.contrib.debug_toolbar_log' in app_names
                and obj and hasattr(obj, 'input_logged_request_toolbar')):
            form_fieldsets.append((None, {'fields': ('debug_toolbar',)}))
        return form_fieldsets

    @short_description(_('user'))
    @filter_by('user_id')
    def user(self, obj):
        return obj.user

    @short_description('')
    def debug_toolbar(self, obj):
        return mark_safe(obj.input_logged_request_toolbar.toolbar)


class OutputRequestsLogISCore(RequestsLogISCore):

    model = OutputLoggedRequest
    abstract = True

    ui_list_fields = (
        'created_at', 'changed_at', 'request_timestamp', 'response_timestamp', 'response_time', 'status',
        'response_code', 'host', 'short_path', 'method', 'slug', 'short_response_body', 'short_request_body',
        'input_logged_request', 'command_log', 'celery_task_run_log', 'short_queries', 'short_request_headers'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('created_at', 'changed_at', 'request_timestamp', 'host', 'method', 'path',
                                   'queries_code', 'request_headers_code', 'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_headers_code',
                                    'response_body_code', 'error_description_code')}),
        (_('Extra information'), {'fields': ('slug', 'response_time', 'input_logged_request',
                                             'display_related_objects')}),
    )


class CommandLogISCore(DisplayRelatedObjectsMixin, UIRESTModelISCore):

    model = CommandLog

    can_create = can_update = can_delete = False

    ui_list_fields = (
        'created_at', 'changed_at', 'name', 'start', 'stop', 'time', 'executed_from_command_line', 'is_successful'
    )

    form_fieldsets = (
        (None, {
            'fields': ('created_at', 'changed_at', 'name', 'input', 'output_html', 'error_message',
                       'display_related_objects', 'output_logged_requests',),
            'class': 'col-sm-6'
        }),
        (None, {
            'fields': ('start', 'stop', 'time', 'executed_from_command_line', 'is_successful'),
            'class': 'col-sm-6'
        }),
    )

    abstract = True

    @short_description(_('output'))
    def output_html(self, obj=None):
        if obj and obj.output is not None:
            conv = Ansi2HTMLConverter()
            output = mark_safe(conv.convert(obj.output, full=False))
            return display_as_code(output)
        return None


class CeleryTaskLogTabs(TabsViewMixin):

    tabs = (
        TabItem('list-celerytasklog', _('celery task')),
        TabItem('list-celerytaskrunlog', _('celery task run')),
    )


class CeleryTaskLogTableView(CeleryTaskLogTabs, TableView):
    pass


class CeleryTaskRunLogISCore(DisplayRelatedObjectsMixin, UIRESTModelISCore):

    model = CeleryTaskRunLog

    abstract = True

    can_create = can_update = can_delete = False

    rest_paginator = BaseOffsetPaginatorWithoutTotal
    rest_extra_filter_fields = (
        'celery_task_id',
    )

    ui_list_fields = (
        'created_at', 'changed_at', 'name', 'state', 'start', 'stop', 'time', 'result', 'retries', 'get_task_log'
    )

    form_fields = (
        'start', 'stop', 'time', 'state', 'result', 'error_message', 'output_html', 'retries',
        'estimated_time_of_next_retry', 'output_logged_requests', 'display_related_objects'
    )

    ui_list_view = CeleryTaskLogTableView

    default_ordering = ('-created_at',)

    @short_description(_('output'))
    def output_html(self, obj=None):
        if obj and obj.output is not None:
            conv = Ansi2HTMLConverter()
            output = mark_safe(conv.convert(obj.output, full=False))
            return display_as_code(output)
        return None


class CeleryTaskRunLogInlineTableView(InlineTableView):

    model = CeleryTaskRunLog
    fields = (
        'created_at', 'changed_at', 'start', 'stop', 'time', 'state', 'result', 'retries'
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


CeleryTaskLog.get_state.filter = CeleryTaskLogStateFilter


class CeleryTaskLogISCore(DisplayRelatedObjectsMixin, UIRESTModelISCore):

    model = CeleryTaskLog

    abstract = True

    can_create = can_update = can_delete = False

    rest_paginator = BaseOffsetPaginatorWithoutTotal

    ui_list_fields = (
        'created_at', 'changed_at', 'name', 'short_input', 'get_state', 'get_start', 'get_stop', 'queue_name'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'created_at', 'changed_at', 'name', 'get_state', 'get_start', 'get_stop',
                'estimated_time_of_first_arrival', 'expires', 'stale', 'queue_name', 'input', 'display_related_objects'
            )
        }),
        (_('celery task runs'), {'inline_view': CeleryTaskRunLogInlineTableView}),
    )

    ui_list_view = CeleryTaskLogTableView

    @filter_by('input')
    @order_by('input')
    @short_description(_('input'))
    def short_input(self, obj=None):
        return truncatechars(obj.input, 50)

    def is_active_menu_item(self, request, active_group):
        return active_group in {
            self.menu_group,
            'celerytaskrunlog',
        }
