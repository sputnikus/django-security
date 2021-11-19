import re
import json
from json import JSONDecodeError

from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import localtime

from generic_m2m_field.models import MultipleDBGenericManyToManyField

from chamber.models import SmartQuerySet

from enumfields import NumEnumField

from security.enums import (
    LoggerName, RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)


def display_json(value, indent=4):
    return json.dumps(value, indent=indent, ensure_ascii=False, cls=DjangoJSONEncoder)


class BaseLogQuerySet(SmartQuerySet):

    def filter_related_with_object(self, related_object):
        return self.filter(
            related_objects__object_id=related_object.pk,
            related_objects__object_ct_id=ContentType.objects.get_for_model(related_object).pk
        )


class Log(models.Model):

    id = models.UUIDField(
        verbose_name=_('log ID'),
        null=False,
        blank=False,
        max_length=250,
        primary_key=True
    )
    extra_data = models.JSONField(
        verbose_name=_('response headers'),
        null=True,
        blank=True,
        encoder=DjangoJSONEncoder
    )
    slug = models.CharField(
        verbose_name=_('slug'),
        null=True,
        blank=True,
        db_index=True,
        max_length=255
    )
    start = models.DateTimeField(
        verbose_name=_('start'),
        blank=False,
        null=False,
        editable=False
    )
    stop = models.DateTimeField(
        verbose_name=_('stop'),
        blank=True,
        null=True,
        editable=False
    )
    time = models.FloatField(
        verbose_name=_('response time'),
        null=True,
        blank=True
    )
    release = models.CharField(
        verbose_name=_('release'),
        null=True,
        blank=True,
        db_index=True,
        max_length=255
    )

    def save(self, update_fields=None, *args, **kwargs):
        if not self.time and self.start and self.stop:
            self.time = (self.stop - self.start).total_seconds()
            if update_fields:
                update_fields = list(update_fields) + ['time']
        super().save(update_fields=update_fields, *args, **kwargs)

    class Meta:
        abstract = True


class RequestLog(Log):

    host = models.CharField(_('host'), max_length=255, null=False, blank=False, db_index=True)
    method = models.SlugField(_('method'), max_length=7, null=False, blank=False, db_index=True)
    path = models.CharField(_('URL path'), max_length=2000, null=False, blank=True, db_index=True)
    queries = models.JSONField(_('queries'), null=True, blank=True, encoder=DjangoJSONEncoder)
    is_secure = models.BooleanField(_('HTTPS connection'), default=False, null=False, blank=False)

    # Request information
    request_headers = models.JSONField(_('request headers'), null=True, blank=True, encoder=DjangoJSONEncoder)
    request_body = models.TextField(_('request body'), null=True, blank=True)

    # Response information
    response_code = models.PositiveSmallIntegerField(_('response code'), null=True, blank=True)
    response_headers = models.JSONField(_('response headers'), null=True, blank=True, encoder=DjangoJSONEncoder)
    response_body = models.TextField(_('response body'), null=True, blank=True)

    state = NumEnumField(verbose_name=_('state'), enum=RequestLogState, null=False, blank=False,
                         default=RequestLogState.INCOMPLETE)
    error_message = models.TextField(_('error description'), null=True, blank=True)

    def __str__(self):
        return ' '.join(
            (force_text(v) for v in (
                self.slug, self.response_code, localtime(self.start.replace(microsecond=0))
            ) if v)
        )

    class Meta:
        abstract = True


class InputRequestLog(RequestLog):

    user_id = models.TextField(verbose_name=_('user ID'), null=True, blank=True, db_index=True)
    ip = models.GenericIPAddressField(_('IP address'), null=False, blank=False, db_index=True)
    view_slug = models.CharField(_('view slug'), null=True, blank=True, db_index=True, max_length=255)

    related_objects = MultipleDBGenericManyToManyField()

    objects = BaseLogQuerySet.as_manager()

    class Meta:
        verbose_name = _('input logged request')
        verbose_name_plural = _('input logged requests')
        ordering = ('-start',)

    @cached_property
    def user(self):
        return get_user_model().objects.filter(pk=self.user_id).first()


class OutputRequestLog(RequestLog):

    related_objects = MultipleDBGenericManyToManyField()

    objects = BaseLogQuerySet.as_manager()

    class Meta:
        verbose_name = _('output logged request')
        verbose_name_plural = _('output logged requests')
        ordering = ('-start',)

    class SmartMeta:
        is_cleaned_pre_save = False


class CommandLog(Log):
    """
    Represents a log of a command run.

    Attributes:
        start: Date and time when command was started.
        stop: Date and time when command finished.
        time: Command processing time in miliseconds.
        name: Name of the command.
        options: Arguments/options the command was run with.
        is_executed_from_command_line: Flag that indicates if command was run from the command line.
        output: Standard and error output of the command.
        is_successful: Flag that indicates if command finished successfully.
    """
    name = models.CharField(max_length=250, blank=False, null=False, editable=False, db_index=True,
                            verbose_name=_('name'))
    input = models.TextField(verbose_name=_('input'), blank=False, null=False, editable=False)
    is_executed_from_command_line = models.BooleanField(verbose_name=_('is executed from command line'),
                                                        blank=False, null=False, default=False, editable=False)
    output = models.TextField(verbose_name=_('output'), blank=True, null=True, editable=False)
    state = NumEnumField(
        verbose_name=_('state'),
        null=False,
        blank=False,
        enum=CommandState,
        default=CommandState.ACTIVE,
        db_index=True
    )
    error_message = models.TextField(verbose_name=_('error message'), null=True, blank=True, editable=False)
    related_objects = MultipleDBGenericManyToManyField()

    objects = BaseLogQuerySet.as_manager()

    class Meta:
        verbose_name = _('command log')
        verbose_name_plural = _('command logs')
        ordering = ('-start',)


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


class CeleryTaskInvocationLog(Log):

    celery_task_id = models.UUIDField(
        verbose_name=_('invocation ID'),
        max_length=250,
        db_index=True,
        null=True,
        blank=True
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
        verbose_name=_('is duplicate'),
        null=True, blank=True
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

    objects = CeleryTaskInvocationLogManager.from_queryset(BaseLogQuerySet)()

    class Meta:
        verbose_name = _('celery task')
        verbose_name_plural = _('celery tasks')
        ordering = ('-start',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.state.label)

    @property
    def runs(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id)

    @property
    def last_run(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id).first()

    @property
    def first_run(self):
        return CeleryTaskRunLog.objects.filter(celery_task_id=self.celery_task_id).last()


class CeleryTaskRunLog(Log):

    celery_task_id = models.UUIDField(
        verbose_name=_('invocation ID'),
        max_length=250,
        db_index=True,
        null=True,
        blank=True
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
    state = NumEnumField(
        verbose_name=_('state'),
        null=False,
        blank=False,
        enum=CeleryTaskRunLogState,
        default=CeleryTaskRunLogState.ACTIVE,
        db_index=True
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
    waiting_time = models.FloatField(
        verbose_name=_('waiting time'),
        null=True,
        blank=True
    )
    related_objects = MultipleDBGenericManyToManyField()

    objects = BaseLogQuerySet.as_manager()

    class Meta:
        verbose_name = _('celery task run')
        verbose_name_plural = _('celery tasks run')
        ordering = ('-start',)

    def __str__(self):
        return '{} ({})'.format(self.name, self.get_state_display())

    def get_task_invocation_logs(self):
        return CeleryTaskInvocationLog.objects.filter(celery_task_id=self.celery_task_id)


def get_response_state(status_code):
    if status_code >= 500:
        return RequestLogState.ERROR
    elif status_code >= 400:
        return RequestLogState.WARNING
    else:
        return RequestLogState.INFO


logger_name_to_log_model = {
    LoggerName.INPUT_REQUEST: InputRequestLog,
    LoggerName.OUTPUT_REQUEST: OutputRequestLog,
    LoggerName.COMMAND: CommandLog,
    LoggerName.CELERY_TASK_INVOCATION: CeleryTaskInvocationLog,
    LoggerName.CELERY_TASK_RUN: CeleryTaskRunLog,
}


def get_log_model_from_logger_name(logger_name):
    return logger_name_to_log_model[logger_name]
