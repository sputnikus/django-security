import json

from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template.defaultfilters import truncatechars
from django.utils.encoding import force_text
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import localtime

from generic_m2m_field.models import MultipleDBGenericManyToManyField

from chamber.models import SmartModel

from enumfields import NumEnumField

from .enums import InputLoggedRequestType, LoggedRequestStatus, CeleryTaskInvocationLogState, CeleryTaskRunLogState


def display_json(value, indent=4):
    return json.dumps(value, indent=indent, ensure_ascii=False, cls=DjangoJSONEncoder)


class LoggedRequest(SmartModel):

    host = models.CharField(_('host'), max_length=255, null=False, blank=False, db_index=True)
    method = models.SlugField(_('method'), max_length=7, null=False, blank=False, db_index=True)
    path = models.CharField(_('URL path'), max_length=2000, null=False, blank=True, db_index=True)
    queries = models.JSONField(_('queries'), null=True, blank=True, encoder=DjangoJSONEncoder)
    is_secure = models.BooleanField(_('HTTPS connection'), default=False, null=False, blank=False)
    slug = models.CharField(_('slug'), null=True, blank=True, db_index=True, max_length=255)

    # Request information
    request_timestamp = models.DateTimeField(_('request timestamp'), null=False, blank=False, db_index=True)
    request_headers = models.JSONField(_('request headers'), null=True, blank=True, encoder=DjangoJSONEncoder)
    request_body = models.TextField(_('request body'), null=False, blank=True)

    # Response information
    response_timestamp = models.DateTimeField(_('response timestamp'), null=True, blank=True, db_index=True)
    response_code = models.PositiveSmallIntegerField(_('response code'), null=True, blank=True)
    response_headers = models.JSONField(_('response headers'), null=True, blank=True, encoder=DjangoJSONEncoder)
    response_body = models.TextField(_('response body'), null=True, blank=True)
    response_time = models.FloatField(_('response time'), null=True, blank=True)

    status = NumEnumField(verbose_name=_('status'), enum=LoggedRequestStatus, null=False, blank=False,
                          default=LoggedRequestStatus.INCOMPLETE)
    error_description = models.TextField(_('error description'), null=True, blank=True)
    exception_name = models.CharField(_('exception name'), null=True, blank=True, max_length=255)

    def short_queries(self):
        return truncatechars(display_json(self.queries, indent=0), 50)
    short_queries.short_description = _('queries')
    short_queries.filter_by = 'queries'

    def short_request_headers(self):
        return truncatechars(display_json(self.request_headers, indent=0), 50)
    short_request_headers.short_description = _('request headers')
    short_request_headers.filter_by = 'request_headers'

    def short_path(self):
        return truncatechars(self.path, 50)
    short_path.short_description = _('Path')
    short_path.filter_by = 'path'
    short_path.order_by = 'path'

    def short_response_body(self):
        return truncatechars(self.response_body, 50) if self.response_body is not None else None
    short_response_body.short_description = _('response body')
    short_response_body.filter_by = 'response_body'

    def short_request_body(self):
        return truncatechars(self.request_body, 50)
    short_request_body.short_description = _('request body')
    short_request_body.filter_by = 'request_body'

    def __str__(self):
        return ' '.join(
            (force_text(v) for v in (
                self.slug, self.response_code, localtime(self.request_timestamp.replace(microsecond=0))
            ) if v)
        )

    class Meta:
        abstract = True

    class UIMeta:
        default_ui_filter_by = 'id'


class InputLoggedRequest(LoggedRequest):

    user_id = models.TextField(verbose_name=_('user ID'), null=True, blank=True, db_index=True)
    ip = models.GenericIPAddressField(_('IP address'), null=False, blank=False, db_index=True)
    type = NumEnumField(verbose_name=_('type'), enum=InputLoggedRequestType,
                        default=InputLoggedRequestType.COMMON_REQUEST,
                        null=False, blank=False, db_index=True)
    related_objects = MultipleDBGenericManyToManyField()

    class Meta:
        verbose_name = _('input logged request')
        verbose_name_plural = _('input logged requests')
        ordering = ('-created_at',)

    class SmartMeta:
        is_cleaned_pre_save = False

    @cached_property
    def user(self):
        return get_user_model().objects.filter(pk=self.user_id).first()


class OutputLoggedRequest(LoggedRequest):

    related_objects = MultipleDBGenericManyToManyField()

    class Meta:
        verbose_name = _('output logged request')
        verbose_name_plural = _('output logged requests')
        ordering = ('-created_at',)

    class SmartMeta:
        is_cleaned_pre_save = False


class CommandLog(SmartModel):
    """
    Represents a log of a command run.

    Attributes:
        start: Date and time when command was started.
        stop: Date and time when command finished.
        time: Command processing time in miliseconds.
        name: Name of the command.
        options: Arguments/options the command was run with.
        executed_from_command_line: Flag that indicates if command was run from the command line.
        output: Standard and error output of the command.
        is_successful: Flag that indicates if command finished successfully.
    """
    start = models.DateTimeField(verbose_name=_('start'), blank=False, null=False, editable=False)
    stop = models.DateTimeField(verbose_name=_('stop'), blank=True, null=True, editable=False)
    time = models.FloatField(verbose_name=_('time'), null=True, blank=True)
    name = models.CharField(max_length=250, blank=False, null=False, editable=False, db_index=True,
                            verbose_name=_('name'))
    input = models.TextField(verbose_name=_('input'), blank=False, null=False, editable=False)
    executed_from_command_line = models.BooleanField(verbose_name=_('executed from command line'),
                                                     blank=False, null=False, default=False, editable=False)
    output = models.TextField(verbose_name=_('output'), blank=True, null=True, editable=False)
    is_successful = models.BooleanField(verbose_name=_('finished successfully'),
                                        blank=False, null=False, default=False, editable=False)
    error_message = models.TextField(verbose_name=_('error message'), null=True, blank=True, editable=False)
    related_objects = MultipleDBGenericManyToManyField()

    class Meta:
        verbose_name = _('command log')
        verbose_name_plural = _('command logs')
        ordering = ('-created_at',)

    class UIMeta:
        default_ui_filter_by = 'id'


class CeleryTaskInvocationLogManager(models.Manager):

    def filter_not_started(self):
        return self.filter(
            state__in={
                CeleryTaskInvocationLogState.WAITING,
                CeleryTaskInvocationLogState.TRIGGERED
            }
        )

    def filter_processing(self, related_objects=None, **kwargs):
        qs = self.filter(
            state__in={
                CeleryTaskInvocationLogState.ACTIVE,
                CeleryTaskInvocationLogState.WAITING,
                CeleryTaskInvocationLogState.TRIGGERED
            }
        ).filter(**kwargs)

        if related_objects:
            for related_object in related_objects:
                qs = qs.filter(
                    related_objects__object_id=related_object.pk,
                    related_objects__object_ct_id=ContentType.objects.get_for_model(related_object).pk
                )
        return qs


class CeleryTaskInvocationLog(SmartModel):

    invocation_id = models.CharField(
        verbose_name=_('invocation ID'),
        max_length=250,
        db_index=True,
        unique=True
    )
    celery_task_id = models.CharField(
        verbose_name=_('celery ID'),
        null=True,
        blank=True,
        max_length=250,
        db_index=True
    )
    name = models.CharField(
        verbose_name=_('task name'),
        null=False,
        blank=False,
        max_length=250,
        db_index=True
    )
    queue_name = models.CharField(
        verbose_name=_('queue name'),
        null=True,
        blank=True,
        max_length=250
    )
    applied_at = models.DateTimeField(
        verbose_name=_('applied at'),
        null=False,
        blank=False
    )
    triggered_at = models.DateTimeField(
        verbose_name=_('triggered at'),
        null=True,
        blank=True
    )
    is_unique = models.BooleanField(
        verbose_name=_('is unique')
    )
    is_async = models.BooleanField(
        verbose_name=_('is async')
    )
    is_duplicate = models.BooleanField(
        verbose_name=_('is duplicate')
    )
    is_on_commit = models.BooleanField(
        verbose_name=_('is on commit')
    )
    input = models.TextField(
        verbose_name=_('input'),
        blank=True,
        null=True,
        editable=False
    )
    task_args = models.JSONField(
        verbose_name=_('task args'),
        null=True,
        blank=True,
        editable=False,
        encoder=DjangoJSONEncoder
    )
    task_kwargs = models.JSONField(
        verbose_name=_('task kwargs'),
        null=True,
        blank=True,
        editable=False,
        encoder=DjangoJSONEncoder
    )
    estimated_time_of_first_arrival = models.DateTimeField(
        verbose_name=_('estimated time of first arrival'),
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField(
        verbose_name=_('time of expiration'),
        null=True,
        blank=True
    )
    stale_at = models.DateTimeField(
        verbose_name=_('stale task time'),
        null=True,
        blank=True
    )
    state = NumEnumField(
        verbose_name=_('state'),
        null=False,
        blank=False,
        enum=CeleryTaskInvocationLogState,
        default=CeleryTaskInvocationLogState.WAITING,
        db_index=True
    )

    related_objects = MultipleDBGenericManyToManyField()

    class Meta:
        verbose_name = _('celery task')
        verbose_name_plural = _('celery tasks')
        ordering = ('-created_at',)

    class UIMeta:
        default_ui_filter_by = 'id'

    def __str__(self):
        return '{} ({})'.format(self.name, self.state.label)

    @property
    def runs(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id)

    @property
    def last_run(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id).last()

    @property
    def first_run(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id).first()

    def get_start(self):
        first_run = self.first_run
        return first_run.start if first_run else None
    get_start.short_description = _('start')

    def get_stop(self):
        last_run = self.last_run
        return last_run.stop if last_run else None
    get_stop.short_description = _('stop')


class CeleryTaskRunLog(SmartModel):

    celery_task_id = models.CharField(
        verbose_name=_('celery ID'),
        null=False,
        blank=False,
        max_length=250,
        db_index=True
    )
    start = models.DateTimeField(
        verbose_name=_('start'),
        null=True,
        blank=True
    )
    stop = models.DateTimeField(
        verbose_name=_('stop'),
        null=True,
        blank=True
    )
    time = models.FloatField(
        verbose_name=_('time'),
        null=True,
        blank=True
    )
    state = NumEnumField(
        verbose_name=_('state'),
        null=False,
        blank=False,
        enum=CeleryTaskRunLogState,
        default=CeleryTaskRunLogState.ACTIVE,
        db_index=True
    )
    name = models.CharField(
        verbose_name=_('task name'),
        null=False,
        blank=False,
        max_length=250,
        db_index=True
    )
    task_args = models.JSONField(
        verbose_name=_('task args'),
        null=True,
        blank=True,
        editable=False,
        encoder=DjangoJSONEncoder
    )
    task_kwargs = models.JSONField(
        verbose_name=_('task kwargs'),
        null=True,
        blank=True,
        editable=False,
        encoder=DjangoJSONEncoder
    )
    result = models.JSONField(
        verbose_name=_('result'),
        blank=True,
        null=True,
        editable=False,
        encoder=DjangoJSONEncoder
    )
    error_message = models.TextField(
        verbose_name=_('error message'),
        null=True,
        blank=True
    )
    output = models.TextField(
        verbose_name=_('output'),
        blank=True,
        null=True,
        editable=False
    )
    retries = models.PositiveSmallIntegerField(
        verbose_name=_('retries'),
        null=False,
        blank=False,
        default=0
    )
    estimated_time_of_next_retry = models.DateTimeField(
        verbose_name=_('estimated time of arrival'),
        null=True,
        blank=True
    )
    queue_name = models.CharField(
        verbose_name=_('queue name'),
        null=True,
        blank=True,
        max_length=250
    )
    related_objects = MultipleDBGenericManyToManyField()

    class Meta:
        verbose_name = _('celery task run')
        verbose_name_plural = _('celery tasks run')
        ordering = ('created_at',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.get_state_display())

    def get_task_invocation_logs(self):
        return CeleryTaskInvocationLog.objects.filter(celery_task_id=self.celery_task_id)
