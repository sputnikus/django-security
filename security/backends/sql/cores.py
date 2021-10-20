from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import TextField
from django.db.models.functions import Cast
from django.template.defaultfilters import truncatechars
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder

from pyston.filters.default_filters import SimpleMethodEqualFilter
from pyston.utils.decorators import filter_by, order_by, filter_class

from is_core.generic_views.inlines.inline_table_views import InlineTableView
from is_core.generic_views.mixins import TabItem, TabsViewMixin
from is_core.generic_views.table_views import TableView
from is_core.main import UIRESTModelISCore
from is_core.utils import render_model_objects_with_link, render_model_object_with_link, display_code
from is_core.utils.decorators import short_description, relation

from security.config import settings
from security.backends.sql.models import (
    CommandLog, InputRequestLog, OutputRequestLog, CeleryTaskInvocationLog, CeleryTaskRunLog
)

from ansi2html import Ansi2HTMLConverter


def display_json(value, indent=4):
    return json.dumps(value, indent=indent, ensure_ascii=False, cls=DjangoJSONEncoder)


def display_related_objects(request, related_objects):
    related_object_instances = []
    for related_object in related_objects:
        try:
            related_object_instances.append(related_object.object)
        except (ObjectDoesNotExist, AttributeError):
            pass

    return render_model_objects_with_link(request, related_object_instances)


def get_content_type_pks_of_parent_related_classes():
    return {
        ContentType.objects.get_for_model(model_class).pk
        for model_class in (CommandLog, InputRequestLog, OutputRequestLog, CeleryTaskInvocationLog,
                            CeleryTaskRunLog)
    }


class UsernameUserFilter(SimpleMethodEqualFilter):

    def get_filter_term(self, value, operator_slug, request):
        user_model = get_user_model()
        return {
            'user_id__in': list(
                user_model.objects.filter(
                   **{'{}__contains'.format(user_model.USERNAME_FIELD): value}
                ).annotate(
                    str_id=Cast('id', output_field=TextField())
                ).values_list('str_id', flat=True)
            )
        }


class SecurityISCoreMixin:

    @short_description(_('related objects'))
    def display_related_objects(self, obj, request):
        return display_related_objects(
            request, obj.related_objects.exclude(object_ct_id__in=get_content_type_pks_of_parent_related_classes())
        )

    @short_description(_('source'))
    def display_source(self, obj, request):
        return display_related_objects(
            request, obj.related_objects.filter(object_ct_id__in=get_content_type_pks_of_parent_related_classes())
        )

    @short_description(_('raised output logged requests'))
    def display_output_logged_requests(self, obj, request):
        return render_model_objects_with_link(
            request,
            OutputRequestLog.objects.filter(
                related_objects__object_id=obj.pk,
                related_objects__object_ct_id=ContentType.objects.get_for_model(obj).pk
            )
        )

    @short_description(_('raised command logs'))
    def display_command_logs(self, obj, request):
        return render_model_objects_with_link(
            request,
            CommandLog.objects.filter(
                related_objects__object_id=obj.pk,
                related_objects__object_ct_id=ContentType.objects.get_for_model(obj).pk
            )
        )

    @short_description(_('raised celery task logs'))
    def display_celery_task_invocation_logs(self, obj, request):
        return render_model_objects_with_link(
            request,
            CeleryTaskInvocationLog.objects.filter(
                related_objects__object_id=obj.pk,
                related_objects__object_ct_id=ContentType.objects.get_for_model(obj).pk
            )
        )


class RequestsLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    abstract = True

    can_create = can_update = can_delete = False

    @short_description(_('request body'))
    def request_body_code(self, obj):
        return display_code(obj.request_body) if obj else None

    @short_description(_('response body'))
    def response_body_code(self, obj):
        return display_code(obj.response_body) if obj else None

    @short_description(_('error message'))
    def error_message_code(self, obj):
        return display_code(obj.error_message) if obj else None

    @filter_by('queries')
    @order_by('queries')
    @short_description(_('queries'))
    def short_queries(self, obj):
        return truncatechars(display_json(obj.queries, indent=0), 50)

    @filter_by('request_headers')
    @order_by('request_headers')
    @short_description(_('request headers'))
    def short_request_headers(self, obj):
        return truncatechars(display_json(obj.request_headers, indent=0), 50)

    @filter_by('path')
    @order_by('path')
    @short_description(_('path'))
    def short_path(self, obj):
        return truncatechars(obj.path, 50)

    @filter_by('response_body')
    @order_by('response_body')
    @short_description(_('response body'))
    def short_response_body(self, obj):
        return truncatechars(obj.response_body, 50) if obj.response_body is not None else None

    @filter_by('request_body')
    @order_by('request_body')
    @short_description(_('request body'))
    def short_request_body(self, obj):
        return truncatechars(obj.request_body, 50)


class InputRequestsLogISCore(RequestsLogISCore):

    model = InputRequestLog
    abstract = True

    ui_list_fields = (
        'id', 'start', 'stop', 'time', 'state',
        'response_code', 'host', 'short_path', 'slug', 'ip', 'user', 'method', 'short_response_body',
        'short_request_body', 'short_queries', 'short_request_headers'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('start', 'host', 'method', 'path',
                                   'queries', 'request_headers', 'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('stop', 'response_code', 'state', 'response_headers',
                                    'response_body_code', 'error_message_code')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('slug', 'time', 'display_related_objects',
                                             'display_output_logged_requests', 'display_command_logs',
                                             'display_celery_task_invocation_logs')}),
    )

    def get_form_fieldsets(self, request, obj=None):
        form_fieldsets = list(super().get_form_fieldsets(request, obj))

        app_names = {app.name for app in apps.get_app_configs()}

        if (settings.SHOW_DEBUG_TOOLBAR and 'security.contrib.debug_toolbar_log' in app_names
                and obj and 'debug_toolbar' in obj.extra_data):
            form_fieldsets.append((None, {'fields': ('debug_toolbar',)}))
        return form_fieldsets

    @short_description(_('user'))
    @filter_class(UsernameUserFilter)
    def user(self, obj):
        return obj.user

    @short_description('')
    def debug_toolbar(self, obj):
        return mark_safe(obj.extra_data.debug_toolbar)


class OutputRequestsLogISCore(RequestsLogISCore):

    model = OutputRequestLog
    abstract = True

    ui_list_fields = (
        'id', 'slug', 'host', 'short_path', 'state', 'start', 'stop', 'time', 'method', 'short_queries',
        'response_code', 'short_request_headers', 'short_request_body', 'short_response_headers', 'short_response_body'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'id', 'slug', 'host', 'path', 'state', 'start', 'stop', 'time', 'method', 'is_secure',
            ),
        }),
        (_l('request'), {'fields': ('queries', 'request_headers', 'request_body_code')}),
        (_l('response'), {'fields': ('response_code', 'state', 'response_headers', 'response_body_code')}),
        (_l('output'), {
            'fields': (
                'error_message_code',
            ),
        }),
        (_l('relations'), {
            'fields': (
                'display_source', 'display_related_objects'
            ),
        }),
    )


class CommandLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CommandLog

    can_create = can_update = can_delete = False

    ui_list_fields = (
        'id', 'slug', 'name', 'state', 'stop', 'time'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'id', 'name', 'state', 'start', 'stop', 'time', 'input', 'is_executed_from_command_line',
            ),
        }),
        (_l('output'), {
            'fields': (
                'error_message_code', 'output_html',
            ),
        }),
        (_l('relations'), {
            'fields': (
                'display_source', 'display_output_logged_requests', 'display_celery_task_invocation_logs',
                'display_command_logs', 'display_related_objects'
            ),
        }),
    )

    abstract = True

    @short_description(_('output'))
    def output_html(self, obj=None):
        if obj and obj.output is not None:
            return display_code(mark_safe(Ansi2HTMLConverter().convert(obj.output, full=False)))
        return None

    @short_description(_('error message'))
    def error_message_code(self, obj=None):
        return display_code(obj.error_message) if obj else None


class CeleryTaskInvocationLogTabs(TabsViewMixin):

    tabs = (
        TabItem('list-celerytaskinvocationlog', _('celery task')),
        TabItem('list-celerytaskrunlog', _('celery task run')),
    )


class CeleryTaskInvocationLogTableView(CeleryTaskInvocationLogTabs, TableView):
    pass


class CeleryTaskInvocationTableView(InlineTableView):

    model = CeleryTaskInvocationLog
    fields = (
        'id', 'celery_task_id',
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class CeleryTaskRunLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CeleryTaskRunLog

    abstract = True

    can_create = can_update = can_delete = False
    show_in_menu = False

    rest_extra_filter_fields = (
        'celery_task_id',
    )

    ui_list_fields = (
        'id', 'celery_task_id', 'slug', 'name', 'state', 'start', 'stop', 'time', 'input', 'queue_name'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'id', 'celery_task_id', 'slug', 'name', 'state', 'start', 'stop', 'time', 'input', 'task_args',
                'task_kwargs_', 'retries', 'estimated_time_of_next_retry', 'queue_name'
            ),
        }),
        (_l('output'), {
            'fields': (
                'error_message_code', 'output_html', 'result'
            ),
        }),
        (_l('relations'), {
            'fields': (
                'display_source', 'display_output_logged_requests', 'display_celery_task_invocation_logs',
                'display_command_logs', 'display_related_objects'
            ),
        }),
    )

    ui_list_view = CeleryTaskInvocationLogTableView

    @short_description(_('output'))
    def output_html(self, obj):
        if obj and obj.output is not None:
            conv = Ansi2HTMLConverter()
            output = mark_safe(conv.convert(obj.output, full=False))
            return display_code(output)
        return None

    @short_description(_('error message'))
    def error_message_code(self, obj=None):
        return display_code(obj.error_message) if obj else None


class CeleryTaskRunLogInlineTableView(InlineTableView):

    model = CeleryTaskRunLog
    fields = (
        'start', 'stop', 'time', 'state', 'retries'
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class CeleryTaskInvocationLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CeleryTaskInvocationLog

    abstract = True

    can_create = can_update = can_delete = False

    ui_list_fields = (
        'id', 'celery_task_id', 'name', 'short_input', 'state', 'get_start',
        'get_stop', 'queue_name'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'celery_task_id', 'name', 'state', 'get_start', 'get_stop',
                'estimated_time_of_first_arrival', 'expires_at', 'stale_at', 'queue_name', 'input',
                'display_source', 'applied_at', 'triggered_at', 'is_unique', 'is_async', 'is_duplicate', 'is_on_commit',
                'display_related_objects',
            )
        }),
        (_('celery task runs'), {'inline_view': CeleryTaskRunLogInlineTableView}),
    )

    ui_list_view = CeleryTaskInvocationLogTableView

    @filter_by('input')
    @order_by('input')
    @short_description(_('input'))
    def short_input(self, obj):
        return truncatechars(obj.input, 50)

    def is_active_menu_item(self, request, active_group):
        return active_group in {
            self.menu_group,
            'celerytaskrunlog',
        }
