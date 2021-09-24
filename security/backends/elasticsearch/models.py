import json

from django.db import router
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.utils.functional import cached_property
from django.core.serializers.json import DjangoJSONEncoder

from elasticsearch_dsl import Q
from elasticsearch_dsl import Document, Date, Integer, Keyword, Text, Object, Boolean, Float, CustomField

from security.config import settings
from security.enums import (
    RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState, LoggerName
)
from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated, get_backend_receiver
)

from .app import SecurityElasticsearchBackend


receiver = get_backend_receiver(SecurityElasticsearchBackend.backend_name)


class JSONTextField(CustomField):

    name = 'jsontext'
    builtin_type = Text()

    def serialize(self, data):
        if data is None:
            return None
        elif isinstance(data, str):
            return data
        else:
            return json.dumps(data, cls=DjangoJSONEncoder)


class EnumField(CustomField):

    name = 'enum'
    builtin_type = Keyword()

    def __init__(self, enum):
        self._enum = enum

    def _serialize(self, data):
        return data.name

    def _deserialize(self, data):
        if isinstance(data, self._enum):
            return data
        else:
            return self._enum[data]


class Log(Document):

    extra_data = Object()
    slug = Keyword()
    related_objects = Keyword()
    parent_log = Keyword()
    start = Date()
    stop = Date()
    time = Float()

    def __str__(self):
        return self.id

    def _set_time(self, kwargs):
        start = kwargs.get('start', self.start)
        stop = kwargs.get('stop', self.stop)
        time = kwargs.get('time', self.time)
        if not time and start and stop:
            kwargs['time'] = (stop - start).total_seconds()

    def update(self, **kwargs):
        self._set_time(kwargs)
        return super().update(**kwargs)

    def save(self, **kwargs):
        self._set_time(kwargs)
        return super().save(**kwargs)

    @property
    def id(self):
        return self.meta.id

    @property
    def pk(self):
        return self.id


class RequestLog(Log):

    host = Keyword()
    method = Keyword()
    path = Keyword()
    queries = JSONTextField()
    is_secure = Boolean()

    # Request information
    request_headers = JSONTextField()
    request_body = Text()

    # Response information
    response_code = Keyword()
    response_headers = JSONTextField()
    response_body = Text()

    state = EnumField(enum=RequestLogState)
    error_message = Text()


class InputRequestLog(RequestLog):

    user_id = Keyword()
    ip = Keyword()
    view_slug = Keyword()

    class Index:
        name = '{}-input-request-log'.format(settings.ELASTICSEARCH_DATABASE.get('prefix', 'security'))

    @cached_property
    def user(self):
        return get_user_model().objects.filter(pk=self.user_id).first()


class OutputRequestLog(RequestLog):

    class Index:
        name = '{}-output-request-log'.format(settings.ELASTICSEARCH_DATABASE.get('prefix', 'security'))


class CommandLog(Log):

    name = Keyword()
    input = Text()
    is_executed_from_command_line = Boolean()
    output = Text()
    is_successful = Boolean()
    state = EnumField(enum=CommandState)
    error_message = Text()

    class Index:
        name = '{}-command-log'.format(settings.ELASTICSEARCH_DATABASE.get('prefix', 'security'))


class CeleryTaskInvocationLog(Log):

    celery_task_id = Keyword()
    name = Keyword()
    queue_name = Keyword()
    applied_at = Date()
    triggered_at = Date()
    is_unique = Boolean()
    is_async = Boolean()
    is_duplicate = Boolean()
    is_on_commit = Boolean()
    input = Text()
    task_args = JSONTextField()
    task_kwargs = JSONTextField()
    estimated_time_of_first_arrival = Date()
    expires_at = Date()
    stale_at = Date()
    state = EnumField(enum=CeleryTaskInvocationLogState)

    @property
    def last_run(self):
        runs = CeleryTaskRunLog.search().filter(
            Q('term', celery_task_id=self.celery_task_id)
        ).sort('-start').execute()
        return runs[0] if runs else None

    class Index:
        name = '{}-celery-task-invocation-log'.format(settings.ELASTICSEARCH_DATABASE.get('prefix', 'security'))


class CeleryTaskRunLog(Log):

    celery_task_id = Keyword()
    state = EnumField(enum=CeleryTaskRunLogState)
    name = Keyword()
    input = Text()
    task_args = JSONTextField()
    task_kwargs = JSONTextField()
    result = JSONTextField()
    error_message = Text()
    output = Text()
    retries = Integer()
    estimated_time_of_next_retry = Date()
    queue_name = Keyword()

    class Index:
        name = '{}-celery-task-run-log'.format(settings.ELASTICSEARCH_DATABASE.get('prefix', 'security'))


def _get_content_type(model, using=None):
    return ContentType.objects.db_manager(using).get_for_model(model)


def get_key_from_content_type_and_id(content_type, object_id, model_db=None):
    model_db = model_db or router.db_for_write(content_type.model_class())
    return '|'.join((model_db, str(content_type.pk), str(object_id)))


def get_key_from_object(obj, model_db=None):
    return get_key_from_content_type_and_id(_get_content_type(obj), obj.pk, model_db)


def get_object_from_key(key):
    model_db, content_type_id, object_id = key.split('|')
    return ContentType.objects.get(
        pk=content_type_id
    ).model_class().objects.using(model_db).filter(pk=object_id).first()


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


def get_log_from_key(key):
    logger_name, id = key.split('|')
    return _get_log_model_from_logger_name(logger_name).get(id=id)


def get_log_key(log):
    logger_name = {v: k for k, v in logger_name_to_log_model.items()}[log.__class__]
    return '{}|{}'.format(logger_name, log.meta.id)


@receiver(input_request_started)
def input_request_started_receiver(sender, logger, **kwargs):
    related_objects = [
        get_key_from_object(related_object) for related_object in logger.related_objects
    ]

    input_request_log = InputRequestLog(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=RequestLogState.INCOMPLETE,
        related_objects=related_objects,
        **logger.data
    )
    input_request_log.meta.id = logger.id
    if logger.parent_with_id:
        input_request_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
    input_request_log.save()


@receiver(input_request_finished)
def input_request_finished_receiver(sender, logger, **kwargs):
    input_request_log = InputRequestLog.get(id=logger.id)
    input_request_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=_get_response_state(logger.data['response_code']),
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(input_request_error)
def input_request_error_receiver(sender, logger, **kwargs):
    input_request_log = InputRequestLog.get(id=logger.id)
    input_request_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(output_request_started)
def output_request_started_receiver(sender, logger, **kwargs):
    related_objects = [
        get_key_from_object(related_object) for related_object in logger.related_objects
    ]
    output_request_log = OutputRequestLog(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=RequestLogState.INCOMPLETE,
        related_objects=related_objects,
        **logger.data
    )
    output_request_log.meta.id = logger.id
    if logger.parent_with_id:
        output_request_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
    output_request_log.save()


@receiver(output_request_finished)
def output_request_finished_receiver(sender, logger, **kwargs):
    output_request_log = OutputRequestLog.get(id=logger.id)
    output_request_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=_get_response_state(logger.data['response_code']),
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(output_request_error)
def output_request_error_receiver(sender, logger, **kwargs):
    output_request_log = OutputRequestLog.get(id=logger.id)
    output_request_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=RequestLogState.ERROR,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(command_started)
def command_started_receiver(sender, logger, **kwargs):
    related_objects = [
        get_key_from_object(related_object) for related_object in logger.related_objects
    ]
    command_log = CommandLog(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CommandState.ACTIVE,
        related_objects=related_objects,
        **logger.data
    )
    command_log.meta.id = logger.id
    if logger.parent_with_id:
        command_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
    command_log.save()


@receiver(command_output_updated)
def command_output_updated_receiver(sender, logger, **kwargs):
    command_log = CommandLog.get(id=logger.id)
    command_log.update(
        slug=logger.slug,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(command_finished)
def command_finished_receiver(sender, logger, **kwargs):
    command_log = CommandLog.get(id=logger.id)
    command_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CommandState.SUCCEEDED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(command_error)
def command_error_receiver(sender, logger, **kwargs):
    command_log = CommandLog.get(id=logger.id)
    command_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CommandState.FAILED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(celery_task_invocation_started)
def celery_task_invocation_started_receiver(sender, logger, **kwargs):
    related_objects = [
        get_key_from_object(related_object) for related_object in logger.related_objects
    ]
    celery_task_invocation_log = CeleryTaskInvocationLog(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskInvocationLogState.WAITING,
        related_objects=related_objects,
        **logger.data
    )
    celery_task_invocation_log.meta.id = logger.id
    if logger.parent_with_id:
        celery_task_invocation_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
    celery_task_invocation_log.save()


@receiver(celery_task_invocation_triggered)
def celery_task_invocation_triggered_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
    celery_task_invocation_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskInvocationLogState.TRIGGERED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(celery_task_invocation_ignored)
def celery_task_invocation_ignored_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
    celery_task_invocation_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskInvocationLogState.IGNORED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(celery_task_invocation_timeout)
def celery_task_invocation_timeout_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
    celery_task_invocation_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskInvocationLogState.TIMEOUT,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(celery_task_invocation_expired)
def celery_task_invocation_expired_receiver(sender, logger, **kwargs):
    celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
    celery_task_invocation_log.update(
        slug=logger.slug,
        state=CeleryTaskInvocationLogState.EXPIRED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )
    if celery_task_invocation_log.celery_task_id:
        CeleryTaskRunLog._index.refresh()
        celery_task_run_log_qs = CeleryTaskRunLog.search().filter(
            Q('term', celery_task_id=celery_task_invocation_log.celery_task_id)
            & Q('term', state=CeleryTaskRunLogState.ACTIVE.name)
        )
        for celery_task_run in celery_task_run_log_qs:
            celery_task_run.update(
                state=CeleryTaskRunLogState.EXPIRED,
                stop=logger.data['stop']
            )


@receiver(celery_task_run_started)
def celery_task_run_started_receiver(sender, logger, **kwargs):
    related_objects = [
        get_key_from_object(related_object) for related_object in logger.related_objects
    ]
    celery_task_run_log = CeleryTaskRunLog(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskRunLogState.ACTIVE,
        related_objects=related_objects,
        **logger.data
    )
    celery_task_run_log.meta.id = logger.id
    if logger.parent_with_id:
        celery_task_run_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
    celery_task_run_log.save()


@receiver(celery_task_run_succeeded)
def celery_task_run_succeeded_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.get(id=logger.id)
    celery_task_run_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskRunLogState.SUCCEEDED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )

    CeleryTaskInvocationLog._index.refresh()
    celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
        'term', celery_task_id=celery_task_run_log.celery_task_id
    ).query(
        Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
        | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
        | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
    )
    for celery_task_invocation in celery_task_invocations_qs:
        celery_task_invocation.update(
            state=CeleryTaskInvocationLogState.SUCCEEDED,
            stop=logger.data['stop'],
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        )


@receiver(celery_task_run_failed)
def celery_task_run_failed_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.get(id=logger.id)
    celery_task_run_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskRunLogState.FAILED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )

    CeleryTaskInvocationLog._index.refresh()
    celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
        'term', celery_task_id=celery_task_run_log.celery_task_id
    ).query(
        Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
        | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
        | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
    )
    for celery_task_invocation in celery_task_invocations_qs:
        celery_task_invocation.update(
            state=CeleryTaskInvocationLogState.FAILED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            stop=logger.data['stop']
        )


@receiver(celery_task_run_retried)
def celery_task_run_retried_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.get(id=logger.id)
    celery_task_run_log.update(
        slug=logger.slug,
        extra_data=logger.extra_data,
        state=CeleryTaskRunLogState.RETRIED,
        refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
        **logger.data
    )


@receiver(celery_task_run_output_updated)
def celery_task_run_output_updated_receiver(sender, logger, **kwargs):
    celery_task_run_log = CeleryTaskRunLog.get(id=logger.id)
    celery_task_run_log.update(
        slug=logger.slug,
        **logger.data,
    )


def get_logs_related_with_object(logger_name, related_object):
    related_object_key = get_key_from_object(related_object)
    return list(_get_log_model_from_logger_name(logger_name).search().filter(
        Q('term', related_objects=related_object_key)
    ))
