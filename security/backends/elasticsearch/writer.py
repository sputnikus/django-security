from elasticsearch_dsl import Q

from security.config import settings
from security.enums import (
    RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)
from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated
)

from .app import SecurityElasticsearchBackend
from .models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog, get_key_from_object,
    get_response_state
)


def set_writer(receiver):

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
            state=get_response_state(logger.data['response_code']),
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )


    @receiver(input_request_error)
    def input_request_error_receiver(sender, logger, **kwargs):
        input_request_log = InputRequestLog.get(id=logger.id)
        input_request_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
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
            state=get_response_state(logger.data['response_code']),
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
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
            update_only_changed_fields=True,
            **logger.data
        )


    @receiver(celery_task_invocation_expired)
    def celery_task_invocation_expired_receiver(sender, logger, **kwargs):
        celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
        celery_task_invocation_log.update(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.EXPIRED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
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
        logger.backend_logs.elasticsearch = celery_task_run_log
        celery_task_run_log.save()

    @receiver(celery_task_run_succeeded)
    def celery_task_run_succeeded_receiver(sender, logger, **kwargs):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.SUCCEEDED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
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
                update_only_changed_fields=True,
            )

    @receiver(celery_task_run_failed)
    def celery_task_run_failed_receiver(sender, logger, **kwargs):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.FAILED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
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
                stop=logger.data['stop'],
                update_only_changed_fields=True,
            )

    @receiver(celery_task_run_retried)
    def celery_task_run_retried_receiver(sender, logger, **kwargs):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.RETRIED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    @receiver(celery_task_run_output_updated)
    def celery_task_run_output_updated_receiver(sender, logger, **kwargs):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data,
        )
