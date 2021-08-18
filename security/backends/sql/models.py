import re
import json
from json import JSONDecodeError

from django.conf import settings as django_settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.template.defaultfilters import truncatechars
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import localtime, now
from django.urls import get_resolver

from generic_m2m_field.models import MultipleDBGenericManyToManyField

from chamber.models import SmartQuerySet

from enumfields import NumEnumField

from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated, get_backend_receiver
)
from security.config import settings
from security.enums import (
    LoggerName, RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)

from .app import SecuritySQLBackend


receiver = get_backend_receiver(SecuritySQLBackend.backend_name)


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

    def save(self, *args, **kwargs):
        if not self.time and self.start and self.stop:
            self.time = (self.stop - self.start).total_seconds()
        super().save(*args, **kwargs)

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


def _get_response_state(status_code):
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


def _get_log_model_from_logger_name(logger_name):
    return logger_name_to_log_model[logger_name]


@receiver(input_request_started)
def input_request_started_receiver(sender, logger, **kwargs):
    input_request_log = InputRequestLog.objects.create(
        id=logger.id,
        slug=logger.slug,
        state=RequestLogState.INCOMPLETE,
        extra_data=logger.extra_data,
        **logger.data
    )
    input_request_log.related_objects.add(*logger.related_objects)
    if logger.parent_with_id:
        input_request_log.related_objects.create(
            object_ct_id=ContentType.objects.get_for_model(
                _get_log_model_from_logger_name(logger.parent_with_id.name)
            ).pk,
            object_id=logger.parent_with_id.id
        )


@receiver(input_request_finished)
def input_request_finished_receiver(sender, logger, **kwargs):
    input_request_log, _ = InputRequestLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=_get_response_state(logger.data['response_code']),
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    input_request_log.related_objects.add(*logger.related_objects)


@receiver(input_request_error)
def input_request_error_receiver(sender, logger, **kwargs):
    input_request_log, _ = InputRequestLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    input_request_log.related_objects.add(*logger.related_objects)


@receiver(output_request_started)
def output_request_started_receiver(sender, logger, **kwargs):
    output_request_log = OutputRequestLog.objects.create(
        id=logger.id,
        state=RequestLogState.INCOMPLETE,
        extra_data=logger.extra_data,
        **logger.data
    )
    output_request_log.related_objects.add(*logger.related_objects)
    if logger.parent_with_id:
        output_request_log.related_objects.create(
            object_ct_id=ContentType.objects.get_for_model(
                _get_log_model_from_logger_name(logger.parent_with_id.name)
            ).pk,
            object_id=logger.parent_with_id.id
        )


@receiver(output_request_finished)
def output_request_finished_receiver(sender, logger, **kwargs):
    output_request_log, _ = OutputRequestLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=_get_response_state(logger.data['response_code']),
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    output_request_log.related_objects.add(*logger.related_objects)


@receiver(output_request_error)
def output_request_error_receiver(sender, logger, **kwargs):
    output_request_log, _ = OutputRequestLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=RequestLogState.ERROR,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    output_request_log.related_objects.add(*logger.related_objects)


@receiver(command_started)
def command_started_receiver(sender, logger, **kwargs):
    command_log = CommandLog.objects.create(
        id=logger.id,
        slug=logger.slug,
        state=CommandState.ACTIVE,
        extra_data=logger.extra_data,
        **logger.data
    )
    command_log.related_objects.add(*logger.related_objects)
    if logger.parent_with_id:
        command_log.related_objects.create(
            object_ct_id=ContentType.objects.get_for_model(
                _get_log_model_from_logger_name(logger.parent_with_id.name)
            ).pk,
            object_id=logger.parent_with_id.id
        )


@receiver(command_output_updated)
def command_output_updated_receiver(sender, logger, **kwargs):
    CommandLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            **logger.data
        )
    )


@receiver(command_finished)
def command_finished_receiver(sender, logger, **kwargs):
    command_log, _ = CommandLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CommandState.SUCCEEDED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    command_log.related_objects.add(*logger.related_objects)


@receiver(command_error)
def command_error_receiver(sender, logger, **kwargs):
    command_log, _ = CommandLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CommandState.FAILED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    command_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_invocation_started)
def celery_task_invocation_started_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.objects.create(
        id=logger.id,
        slug=logger.slug,
        state=CeleryTaskInvocationLogState.WAITING,
        extra_data=logger.extra_data,
        **logger.data
    )
    celery_task_invocation_log.related_objects.add(*logger.related_objects)
    if logger.parent_with_id:
        celery_task_invocation_log.related_objects.create(
            object_ct_id=ContentType.objects.get_for_model(
                _get_log_model_from_logger_name(logger.parent_with_id.name)
            ).pk,
            object_id=logger.parent_with_id.id
        )


@receiver(celery_task_invocation_triggered)
def celery_task_invocation_triggered_receiver(sender, logger, **kwargs):
    celery_task_invocation_log, _ = CeleryTaskInvocationLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.TRIGGERED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    celery_task_invocation_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_invocation_ignored)
def celery_task_invocation_ignored_receiver(sender, logger, **kwargs):
    celery_task_invocation_log, _ = CeleryTaskInvocationLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.IGNORED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    celery_task_invocation_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_invocation_timeout)
def celery_task_invocation_timeout_receiver(sender, logger, **kwargs):
    celery_task_invocation_log, _ = CeleryTaskInvocationLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.TIMEOUT,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    celery_task_invocation_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_invocation_expired)
def celery_task_invocation_expired_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.EXPIRED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )[0]
    celery_task_invocation_log.runs.filter(
        state=CeleryTaskRunLogState.ACTIVE
    ).change_and_save(
        state=CeleryTaskRunLogState.EXPIRED,
        stop=logger.data['stop']
    )
    celery_task_invocation_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_run_started)
def celery_task_run_started_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.objects.create(
        id=logger.id,
        slug=logger.slug,
        state=CeleryTaskRunLogState.ACTIVE,
        extra_data=logger.extra_data,
        **logger.data
    )
    celery_task_run_log.related_objects.add(*logger.related_objects)
    if logger.parent_with_id:
        celery_task_run_log.related_objects.create(
            object_ct_id=ContentType.objects.get_for_model(
                _get_log_model_from_logger_name(logger.parent_with_id.name)
            ).pk,
            object_id=logger.parent_with_id.id
        )


@receiver(celery_task_run_succeeded)
def celery_task_run_succeeded_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskRunLogState.SUCCEEDED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )[0]
    celery_task_run_log.get_task_invocation_logs().filter(state__in={
        CeleryTaskInvocationLogState.WAITING,
        CeleryTaskInvocationLogState.TRIGGERED,
        CeleryTaskInvocationLogState.ACTIVE
    }).change_and_save(
        state=CeleryTaskInvocationLogState.SUCCEEDED,
        stop=logger.data['stop']
    )
    celery_task_run_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_run_failed)
def celery_task_run_failed_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskRunLogState.FAILED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )[0]
    celery_task_run_log.get_task_invocation_logs().filter(state__in={
        CeleryTaskInvocationLogState.WAITING,
        CeleryTaskInvocationLogState.TRIGGERED,
        CeleryTaskInvocationLogState.ACTIVE
    }).change_and_save(
        state=CeleryTaskInvocationLogState.FAILED,
        stop=logger.data['stop']
    )
    celery_task_run_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_run_retried)
def celery_task_run_retried_receiver(sender, logger, **kwargs):
    celery_task_run_log, _ = CeleryTaskRunLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            state=CeleryTaskRunLogState.RETRIED,
            extra_data=logger.extra_data,
            **logger.data
        )
    )
    celery_task_run_log.related_objects.add(*logger.related_objects)


@receiver(celery_task_run_output_updated)
def celery_task_run_output_updated_receiver(sender, logger, **kwargs):
    CeleryTaskRunLog.objects.update_or_create(
        id=logger.id,
        defaults=dict(
            slug=logger.slug,
            **logger.data
        )
    )
