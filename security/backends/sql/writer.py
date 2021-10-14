from django.contrib.contenttypes.models import ContentType

from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated, get_backend_receiver
)
from security.enums import  RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState

from .models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog,
    get_log_model_from_logger_name, get_response_state
)


def set_writer(receiver):
    @receiver(input_request_started)
    def input_request_started_receiver(sender, logger, **kwargs):
        input_request_log = InputRequestLog(
            id=logger.id,
            slug=logger.slug,
            state=RequestLogState.INCOMPLETE,
            extra_data=logger.extra_data,
            **logger.data
        )
        logger.backend_logs.sql = input_request_log
        input_request_log.save()
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
        input_request_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=_get_response_state(logger.data['response_code']),
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        input_request_log.related_objects.add(*logger.related_objects)

    @receiver(input_request_error)
    def input_request_error_receiver(sender, logger, **kwargs):
        input_request_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        input_request_log.related_objects.add(*logger.related_objects)

    @receiver(output_request_started)
    def output_request_started_receiver(sender, logger, **kwargs):
        output_request_log = OutputRequestLog(
            id=logger.id,
            state=RequestLogState.INCOMPLETE,
            extra_data=logger.extra_data,
            **logger.data
        )
        logger.backend_logs.sql = output_request_log
        output_request_log.save()
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
        output_request_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=_get_response_state(logger.data['response_code']),
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        output_request_log.related_objects.add(*logger.related_objects)

    @receiver(output_request_error)
    def output_request_error_receiver(sender, logger, **kwargs):
        output_request_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=RequestLogState.ERROR,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        output_request_log.related_objects.add(*logger.related_objects)

    @receiver(command_started)
    def command_started_receiver(sender, logger, **kwargs):
        command_log = CommandLog(
            id=logger.id,
            slug=logger.slug,
            state=CommandState.ACTIVE,
            extra_data=logger.extra_data,
            **logger.data
        )
        logger.backend_logs.sql = command_log
        command_log.save()
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
        change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            update_only_changed_fields=True,
            **logger.data
        )

    @receiver(command_finished)
    def command_finished_receiver(sender, logger, **kwargs):
        command_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CommandState.SUCCEEDED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        command_log.related_objects.add(*logger.related_objects)

    @receiver(command_error)
    def command_error_receiver(sender, logger, **kwargs):
        command_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CommandState.FAILED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        command_log.related_objects.add(*logger.related_objects)

    @receiver(celery_task_invocation_started)
    def celery_task_invocation_started_receiver(sender, logger, **kwargs):
        celery_task_invocation_log = CeleryTaskInvocationLog(
            id=logger.id,
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.WAITING,
            extra_data=logger.extra_data,
            **logger.data
        )
        logger.backend_logs.sql = celery_task_invocation_log
        celery_task_invocation_log.save()
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
        celery_task_invocation_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.TRIGGERED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        celery_task_invocation_log.related_objects.add(*logger.related_objects)

    @receiver(celery_task_invocation_ignored)
    def celery_task_invocation_ignored_receiver(sender, logger, **kwargs):
        celery_task_invocation_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.IGNORED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        celery_task_invocation_log.related_objects.add(*logger.related_objects)

    @receiver(celery_task_invocation_timeout)
    def celery_task_invocation_timeout_receiver(sender, logger, **kwargs):
        celery_task_invocation_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.TIMEOUT,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
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
        celery_task_run_log = CeleryTaskRunLog(
            id=logger.id,
            slug=logger.slug,
            state=CeleryTaskRunLogState.ACTIVE,
            extra_data=logger.extra_data,
            **logger.data
        )
        logger.backend_logs.sql = celery_task_run_log
        celery_task_run_log.save()
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
        celery_task_run_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskRunLogState.SUCCEEDED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
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
        celery_task_run_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskRunLogState.FAILED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
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
        celery_task_run_log = change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            state=CeleryTaskRunLogState.RETRIED,
            extra_data=logger.extra_data,
            update_only_changed_fields=True,
            **logger.data
        )
        celery_task_run_log.related_objects.add(*logger.related_objects)

    @receiver(celery_task_run_output_updated)
    def celery_task_run_output_updated_receiver(sender, logger, **kwargs):
        change_and_save(
            logger.backend_logs.sql,
            slug=logger.slug,
            update_only_changed_fields=True,
            **logger.data
        )
