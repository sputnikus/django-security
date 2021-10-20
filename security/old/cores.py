from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import TextField
from django.db.models.functions import Cast
from django.template.defaultfilters import truncatechars
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

from pyston.filters.default_filters import SimpleMethodEqualFilter
from pyston.utils.decorators import filter_by, order_by, filter_class

from is_core.generic_views.inlines.inline_table_views import InlineTableView
from is_core.generic_views.mixins import TabItem, TabsViewMixin
from is_core.generic_views.table_views import TableView
from is_core.main import UIRESTModelISCore
from is_core.utils import render_model_objects_with_link, render_model_object_with_link, display_code
from is_core.utils.decorators import short_description, relation

from security.config import settings
from security.models import (
    CommandLog, InputLoggedRequest, OutputLoggedRequest, CeleryTaskInvocationLog, CeleryTaskRunLog
)

from ansi2html import Ansi2HTMLConverter


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
        for model_class in (CommandLog, InputLoggedRequest, OutputLoggedRequest, CeleryTaskInvocationLog,
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
            OutputLoggedRequest.objects.filter(
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

    @short_description(_('error description'))
    def error_description_code(self, obj):
        return display_code(obj.error_description) if obj else None


class InputRequestsLogISCore(RequestsLogISCore):

    model = InputLoggedRequest
    abstract = True
    menu_group = 'old-inputrequestlog'

    ui_list_fields = (
        'id', 'created_at', 'changed_at', 'request_timestamp', 'response_timestamp', 'response_time', 'status',
        'response_code', 'host', 'short_path', 'slug', 'ip', 'user', 'method', 'type', 'short_response_body',
        'short_request_body', 'short_queries', 'short_request_headers'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('created_at', 'changed_at', 'request_timestamp', 'host', 'method', 'path',
                                   'queries', 'request_headers', 'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_headers',
                                    'response_body_code', 'type', 'error_description_code')}),
        (_('User information'), {'fields': ('user', 'ip')}),
        (_('Extra information'), {'fields': ('slug', 'response_time', 'display_related_objects',
                                             'display_output_logged_requests', 'display_command_logs',
                                             'display_celery_task_invocation_logs')}),
    )

    def get_form_fieldsets(self, request, obj=None):
        form_fieldsets = list(super().get_form_fieldsets(request, obj))

        app_names = {app.name for app in apps.get_app_configs()}

        if (settings.SHOW_DEBUG_TOOLBAR and 'security.contrib.debug_toolbar_log' in app_names
                and obj and hasattr(obj, 'input_logged_request_toolbar')):
            form_fieldsets.append((None, {'fields': ('debug_toolbar',)}))
        return form_fieldsets

    @short_description(_('user'))
    @filter_class(UsernameUserFilter)
    def user(self, obj):
        return obj.user

    @short_description('')
    def debug_toolbar(self, obj):
        return mark_safe(obj.input_logged_request_toolbar.toolbar)


class OutputRequestsLogISCore(RequestsLogISCore):

    model = OutputLoggedRequest
    abstract = True
    menu_group = 'old-outputrequestlog'

    ui_list_fields = (
        'id', 'created_at', 'changed_at', 'request_timestamp', 'response_timestamp', 'response_time', 'status',
        'response_code', 'host', 'short_path', 'method', 'slug', 'short_response_body', 'short_request_body',
        'short_queries', 'short_request_headers'
    )

    form_fieldsets = (
        (_('Request'), {'fields': ('created_at', 'changed_at', 'request_timestamp', 'host', 'method', 'path',
                                   'queries', 'request_headers', 'request_body_code', 'is_secure')}),
        (_('Response'), {'fields': ('response_timestamp', 'response_code', 'status', 'response_headers',
                                    'response_body_code', 'error_description_code')}),
        (_('Extra information'), {'fields': ('slug', 'response_time', 'display_related_objects', 'display_source')}),
    )


class CommandLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CommandLog
    menu_group = 'old-commandlog'

    can_create = can_update = can_delete = False

    ui_list_fields = (
        'id', 'created_at', 'changed_at', 'name', 'start', 'stop', 'time', 'executed_from_command_line', 'is_successful'
    )

    form_fieldsets = (
        (
            None, {
                'fieldsets': (
                    (None, {
                        'fields': (
                            'created_at', 'changed_at', 'name', 'input', 'error_message', 'display_related_objects',
                            'display_source', 'display_output_logged_requests', 'display_command_logs',
                            'display_celery_task_invocation_logs'
                        ),
                        'class': 'col-sm-6'
                    }),
                    (None, {
                        'fields': ('start', 'stop', 'time', 'executed_from_command_line', 'is_successful'),
                        'class': 'col-sm-6'
                    })
                )
            }
        ),
        (None, {'fields': ('output_html',)})
    )

    abstract = True

    @short_description(_('output'))
    def output_html(self, obj=None):
        if obj and obj.output is not None:
            return display_code(mark_safe(Ansi2HTMLConverter().convert(obj.output, full=False)))
        return None


class CeleryTaskInvocationLogTabs(TabsViewMixin):

    tabs = (
        TabItem('list-old-celerytaskinvocationlog', _('celery task')),
        TabItem('list-old-celerytaskrunlog', _('celery task run')),
    )


class CeleryTaskInvocationLogTableView(CeleryTaskInvocationLogTabs, TableView):
    pass


class CeleryTaskInvocationTableView(InlineTableView):

    model = CeleryTaskInvocationLog

    fields = (
        'id', 'invocation_id', 'celery_task_id', 'created_at', 'changed_at'
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class CeleryTaskRunLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CeleryTaskRunLog
    menu_group = 'old-celerytaskrunlog'

    abstract = True

    can_create = can_update = can_delete = False
    show_in_menu = False

    rest_extra_filter_fields = (
        'celery_task_id',
    )

    ui_list_fields = (
        'id', 'celery_task_id', 'created_at', 'changed_at', 'name', 'state', 'start', 'stop', 'time', 'retries',
        'queue_name'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'celery_task_id', 'start', 'stop', 'time', 'state', 'result', 'error_message', 'output_html',
                'retries', 'estimated_time_of_next_retry', 'queue_name', 'display_related_objects',
                'display_output_logged_requests',  'display_command_logs', 'display_celery_task_invocation_logs'
            )
        }),
        (_('celery task invocations'), {'inline_view': CeleryTaskInvocationTableView}),
    )

    ui_list_view = CeleryTaskInvocationLogTableView

    default_ordering = ('-created_at',)

    @short_description(_('output'))
    def output_html(self, obj):
        if obj and obj.output is not None:
            conv = Ansi2HTMLConverter()
            output = mark_safe(conv.convert(obj.output, full=False))
            return display_code(output)
        return None


class CeleryTaskRunLogInlineTableView(InlineTableView):

    model = CeleryTaskRunLog
    fields = (
        'created_at', 'changed_at', 'start', 'stop', 'time', 'state', 'retries'
    )

    def _get_list_filter(self):
        return {
            'filter': {
                'celery_task_id': self.parent_instance.celery_task_id
            }
        }


class CeleryTaskInvocationLogISCore(SecurityISCoreMixin, UIRESTModelISCore):

    model = CeleryTaskInvocationLog
    menu_group = 'old-celerytaskinvocationlog'

    abstract = True

    can_create = can_update = can_delete = False

    ui_list_fields = (
        'id', 'invocation_id', 'celery_task_id', 'created_at', 'changed_at', 'name', 'short_input', 'state',
        'get_start', 'get_stop', 'queue_name'
    )

    form_fieldsets = (
        (None, {
            'fields': (
                'invocation_id', 'celery_task_id', 'created_at', 'changed_at', 'name', 'state', 'get_start', 'get_stop',
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
            'old-celerytaskrunlog',
        }
