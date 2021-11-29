import json

from ansi2html import Ansi2HTMLConverter

from django.template.defaultfilters import truncatechars
from django.utils.translation import ugettext_lazy as _
from django.utils.html import mark_safe

from chamber.shortcuts import get_object_or_none

from pyston.utils.decorators import filter_by, order_by

from is_core.utils import display_code, render_model_object_with_link, render_model_objects_with_link
from is_core.utils.decorators import short_description


field_labels = {
    'id': _('ID'),
    'release': _('release'),
    'slug': _('slug'),
    'view_slug': _('view slug'),
    'host': _('host'),
    'path': _('path'),
    'state': _('state'),
    'start': _('start'),
    'stop': _('stop'),
    'time': _('time'),
    'method': _('method'),
    'response_code': _('response code'),
    'ip': _('IP'),
    'is_secure': _('HTTPS connection'),
    'short_path': _('pah'),
    'short_queries': _('queries'),
    'short_request_headers': _('request headers'),
    'short_request_body': _('request body'),
    'short_response_headers': _('response headers'),
    'short_response_body': _('response body'),
    'name': _('name'),
    'input': _('input'),
    'is_executed_from_command_line': _('is executed from command line'),
    'celery_task_id': _('celery task ID'),
    'queue_name': _('queue name'),
    'applied_at': _('applied at'),
    'triggered_at': _('triggered at'),
    'is_unique': _('is unique'),
    'is_async': _('is async'),
    'is_duplicate': _('is duplicate'),
    'is_on_commit': _('is on commit'),
    'estimated_time_of_first_arrival': _('estimated time of first arrival'),
    'expires_at': _('expires at'),
    'stale_at': _('stale at'),
    'retries': _('retries'),
    'estimated_time_of_next_retry': _('estimated time of next retry'),
}


def display_json(value, indent=4):
    dict_value = json.loads(value) if isinstance(value, str) else value
    return json.dumps(dict_value, indent=indent, ensure_ascii=False)


class ChildLogTableViewMixin:

    fields = (
        'id', 'start', 'stop'
    )

    def _get_log_key(self, log):
        raise NotImplementedError

    def _get_list_filter(self):
        return {
            'filter': {
                'parent_log': self._get_log_key(self.parent_instance)
            }
        }


class CeleryTaskInvocationLogInlineTableViewMixin:

    fields = (
        'id', 'start', 'stop', 'time', 'state',
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class CeleryTaskRunLogInlineTableViewMixin:

    fields = (
        'start', 'stop', 'waiting_time', 'time', 'state', 'retries'
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class LogCoreMixin:

    field_labels = field_labels

    default_ordering = ('-start',)
    rest_extra_filter_fields = ('parent_log',)

    can_create = False
    can_read = True
    can_update = False
    can_delete = False

    output_request_inline_table_view = None
    command_inline_table_view = None
    celery_task_invocation_inline_table_view = None

    @short_description(_('error message'))
    @filter_by('error_message')
    def error_message_code(self, obj):
        return display_code(obj.error_message) if obj else None

    @short_description(_('source'))
    def display_source(self, obj, request):
        parent_log_obj = self._get_parent_log_obj(obj)
        return render_model_object_with_link(request, parent_log_obj) if parent_log_obj else None

    def _get_parent_log_obj(self, obj):
        raise NotImplementedError

    def _get_related_objects(self, obj):
        raise NotImplementedError

    @short_description(_('related objects'))
    def display_related_objects(self, obj, request):
        return render_model_objects_with_link(request, self._get_related_objects(obj))

    @short_description(_('revision'))
    def revision(self, obj, request):
        try:
            from reversion.models import get_revision_or_none
        except ImportError:
            def get_revision_or_none(id):
                try:
                    from reversion.models import Revision
                    return get_object_or_none(Revision, pk=id)
                except ImportError:
                    return None

        revision = (
            get_revision_or_none(obj.extra_data['reversion']['revision_id']) if 'reversion' in obj.extra_data else None
        )
        return render_model_object_with_link(request, revision) if revision else None


class RequestLogCoreMixin(LogCoreMixin):

    @filter_by('path')
    @order_by('path')
    @short_description(_('path'))
    def short_path(self, obj):
        return truncatechars(obj.path, 50)

    @filter_by('request_body')
    @order_by('request_body')
    @short_description(_('request body'))
    def short_request_body(self, obj):
        return truncatechars(obj.request_body, 50)

    @filter_by('response_body')
    @order_by('response_body')
    @short_description(_('response body'))
    def short_response_body(self, obj):
        return truncatechars(obj.response_body, 50) if obj.response_body is not None else None

    @filter_by('queries')
    @order_by('queries')
    @short_description(_('queries'))
    def short_queries(self, obj):
        return truncatechars(obj.queries, 50)

    @filter_by('request_headers')
    @order_by('request_headers')
    @short_description(_('request headers'))
    def short_request_headers(self, obj):
        return truncatechars(obj.request_headers, 50)

    @filter_by('request_headers')
    @order_by('request_headers')
    @short_description(_('request headers'))
    def short_response_headers(self, obj):
        return truncatechars(obj.response_headers, 50)

    @short_description(_('request body'))
    def request_body_code(self, obj):
        return display_code(obj.request_body) if obj and obj.request_body else None

    @short_description(_('response body'))
    def response_body_code(self, obj):
        return display_code(obj.response_body) if obj and obj.response_body else None

    @short_description(_('queries'))
    def queries_code(self, obj):
        return display_code(display_json(obj.queries)) if obj and obj.queries else None

    @short_description(_('request headers'))
    def request_headers_code(self, obj):
        return display_code(display_json(obj.request_headers)) if obj and obj.request_headers else None

    @short_description(_('response headers'))
    def response_headers_code(self, obj):
        return display_code(display_json(obj.response_headers)) if obj and obj.response_headers else None


class InputRequestLogCoreMixin(RequestLogCoreMixin):

    menu_group = 'inputrequestlog'

    list_fields = (
        'id', 'start', 'stop', 'release', 'slug', 'view_slug', 'host', 'short_path', 'state', 'time', 'method',
        'short_queries', 'response_code', 'short_request_headers', 'short_request_body', 'short_response_headers',
        'short_response_body', 'user', 'ip',
    )

    verbose_name = _('input request log')
    verbose_name_plural = _('input request logs')

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'fields': (
                    'id', 'release', 'slug', 'view_slug', 'host', 'path', 'state', 'start', 'stop', 'time', 'method',
                    'is_secure', 'user', 'ip'
                ),
            }),
            (_('request'), {'fields': ('queries_code', 'request_headers_code', 'request_body_code')}),
            (_('response'), {'fields': ('response_code', 'state', 'response_headers_code', 'response_body_code')}),
            (_('output'), {
                'fields': (
                    'error_message_code',
                ),
            }),
            (_('relations'), {
                'fieldsets': (
                    (None, {'fields': (
                        'revision', 'display_source', 'display_related_objects'
                    )}),
                    (_('output requests'), {'inline_view': self.output_request_inline_table_view}),
                    (_('commands'), {'inline_view': self.command_inline_table_view}),
                    (_('celery invocations'), {'inline_view': self.celery_task_invocation_inline_table_view}),
                ),
            }),
            (None, {'fields': ('debug_toolbar',)})
        )

    @short_description('')
    def debug_toolbar(self, obj):
        return (
            mark_safe(obj.extra_data.get('debug_toolbar'))
            if obj.extra_data and 'debug_toolbar' in obj.extra_data else ''
        )


class OutputRequestLogCoreMixin(RequestLogCoreMixin):

    menu_group = 'outputrequestlog'

    list_fields = (
        'id', 'start', 'stop', 'release', 'slug', 'host', 'short_path', 'state', 'time', 'method', 'short_queries',
        'response_code', 'short_request_headers', 'short_request_body', 'short_response_headers', 'short_response_body'
    )

    fieldsets = (
        (None, {
            'fields': (
                'id', 'release', 'slug', 'host', 'path', 'state', 'start', 'stop', 'time', 'method', 'is_secure',
            ),
        }),
        (_('request'), {'fields': ('queries_code', 'request_headers_code', 'request_body_code')}),
        (_('response'), {'fields': ('response_code', 'state', 'response_headers_code', 'response_body_code')}),
        (_('output'), {
            'fields': (
                'error_message_code',
            ),
        }),
        (_('relations'), {
            'fields': (
                'display_source', 'display_related_objects'
            ),
        }),
    )

    verbose_name = _('output request log')
    verbose_name_plural = _('output request logs')


class OutputLogCoreMixin:

    @short_description(_('output'))
    def output_html(self, obj=None):
        if obj and obj.output is not None:
            return display_code(mark_safe(Ansi2HTMLConverter().convert(obj.output, full=False)))
        return None


class CommandLogCoreMixin(OutputLogCoreMixin, LogCoreMixin):

    menu_group = 'commandlog'

    list_fields = (
        'id', 'start', 'stop', 'release', 'slug', 'name', 'state', 'time'
    )

    verbose_name = _('command log')
    verbose_name_plural = _('command logs')

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'fields': (
                    'id', 'release', 'slug', 'name', 'state', 'start', 'stop', 'time', 'input',
                    'is_executed_from_command_line',
                ),
            }),
            (_('output'), {
                'fields': (
                    'error_message_code', 'output_html',
                ),
            }),
            (_('relations'), {
                'fieldsets': (
                    (None, {'fields': (
                        'revision', 'display_source', 'display_related_objects'
                    )}),
                    (_('output requests'), {'inline_view': self.output_request_inline_table_view}),
                    (_('commands'), {'inline_view': self.command_inline_table_view}),
                    (_('celery invocations'), {'inline_view': self.celery_task_invocation_inline_table_view}),
                ),
            }),
        )


class CeleryCoreMixin(LogCoreMixin):

    @short_description(_('task args'))
    def task_args_code(self, obj):
        return display_code(display_json(obj.task_args)) if obj and obj.task_args else None

    @short_description(_('task kwargs'))
    def task_kwargs_code(self, obj):
        return display_code(display_json(obj.task_kwargs)) if obj and obj.task_kwargs else None

    @filter_by('input')
    @order_by('input')
    @short_description(_('input'))
    def short_input(self, obj):
        return truncatechars(obj.input, 50)


class CeleryTaskRunLogCoreMixin(OutputLogCoreMixin, CeleryCoreMixin, LogCoreMixin):

    menu_group = 'celerytaskrunlog'

    rest_fields = list_fields = (
        'id', 'start', 'stop', 'release', 'slug', 'celery_task_id', 'name', 'state', 'waiting_time', 'time',
        'short_input', 'queue_name'
    )

    verbose_name = _('celery task run log')
    verbose_name_plural = _('celery task run logs')

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'fields': (
                    'id', 'release', 'celery_task_id', 'slug', 'name', 'state', 'start', 'stop', 'waiting_time', 'time',
                    'input', 'task_args_code', 'task_kwargs_code', 'retries', 'estimated_time_of_next_retry',
                    'queue_name'
                ),
            }),
            (_('output'), {
                'fields': (
                    'error_message_code', 'output_html', 'result_code'
                ),
            }),
            (_('relations'), {
                'fieldsets': (
                    (None, {'fields': (
                        'revision', 'display_related_objects',
                    )}),
                    (_('output requests'), {'inline_view': self.output_request_inline_table_view}),
                    (_('commands'), {'inline_view': self.command_inline_table_view}),
                    (_('celery invocations'), {'inline_view': self.celery_task_invocation_inline_table_view}),
                ),
            }),
        )

    @short_description(_('result'))
    def result_code(self, obj):
        return display_code(display_json(obj.result)) if obj and obj.result else None


class CeleryTaskInvocationLogCoreMixin(CeleryCoreMixin, LogCoreMixin):

    menu_group = 'celerytaskinvocationlog'

    rest_fields = list_fields = (
        'id', 'start', 'stop', 'release', 'slug', 'celery_task_id', 'name', 'state_with_duplicate', 'time',
        'short_input', 'queue_name'
    )

    celery_task_run_inline_table_view = None

    verbose_name = _('celery task invocation log')
    verbose_name_plural = _('celery task invocation logs')

    @filter_by('state')
    @order_by('state')
    @short_description(_('state'))
    def state_with_duplicate(self, obj):
        return '{} ({})'.format(obj.state.label, _('duplicate')) if obj.is_duplicate else obj.state.label

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {
                'fields': (
                    'id', 'release', 'celery_task_id', 'slug', 'name', 'state_with_duplicate', 'start', 'stop', 'time',
                    'input', 'task_args_code', 'task_kwargs_code', 'applied_at', 'triggered_at', 'queue_name',
                    'is_unique', 'is_async', 'is_duplicate', 'is_on_commit', 'estimated_time_of_first_arrival',
                    'expires_at', 'stale_at'
                ),
            }),
            (_('celery task runs'), {'inline_view': self.celery_task_run_inline_table_view}),
            (_('relations'), {
                'fields': (
                    'display_source', 'display_related_objects'
                ),
            }),
        )
