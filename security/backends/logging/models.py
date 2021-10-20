import logging

from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated, get_backend_receiver
)


receiver = get_backend_receiver('logging')


input_request_logger = logging.getLogger('security.input_request')
output_request_logger = logging.getLogger('security.output_request')
command_logger = logging.getLogger('security.command')
celery_logger = logging.getLogger('security.celery')


@receiver(input_request_started)
def input_request_started_receiver(sender, logger, **kwargs):
    input_request_logger.info(
        'Input request "%(id)s" to "%(host)s" with path "%(path)s" was started',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            input_request_id=logger.id,
            input_request_host=logger.data['host'],
            input_request_path=logger.data['path'],
            input_request_method=logger.data['method'],
            input_request_view_slug=logger.data['view_slug'],
            input_request_slug=logger.slug,
            input_request_is_secure=logger.data['is_secure'],
            input_request_ip=logger.data['ip'],
        )
    )


@receiver(input_request_finished)
def input_request_finished_receiver(sender, logger, **kwargs):
    input_request_logger.info(
        'Input request "%(id)s" to "%(host)s" with path "%(path)s" was finished',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            input_request_id=logger.id,
            input_request_host=logger.data['host'],
            input_request_path=logger.data['path'],
            input_request_method=logger.data['method'],
            input_request_view_slug=logger.data['view_slug'],
            input_request_slug=logger.slug,
            input_request_is_secure=logger.data['is_secure'],
            input_request_ip=logger.data['ip'],
            input_request_response_code=logger.data['response_code'],
            input_request_start=logger.data['start'],
            input_request_stop=logger.data['stop'],
            input_request_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
        )
    )


@receiver(input_request_error)
def input_request_error_receiver(sender, logger, **kwargs):
    input_request_logger.error(
        'Input request "%(id)s" to "%(host)s" with path "%(path)s" failed',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            input_request_id=logger.id,
            input_request_host=logger.data['host'],
            input_request_path=logger.data['path'],
            input_request_method=logger.data['method'],
            input_request_view_slug=logger.data['view_slug'],
            input_request_slug=logger.slug,
            input_request_is_secure=logger.data['is_secure'],
            input_request_ip=logger.data['ip'],
            input_request_start=logger.data['start'],
        )
    )


@receiver(output_request_started)
def output_request_started_receiver(sender, logger, **kwargs):
    output_request_logger.info(
        'Output request "%(id)s" to "%(host)s" with path "%(path)s" was started',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            output_request_id=logger.id,
            output_request_host=logger.data['host'],
            output_request_path=logger.data['path'],
            output_request_method=logger.data['method'],
            output_request_slug=logger.slug,
            output_request_is_secure=logger.data['is_secure'],
        )
    )


@receiver(output_request_finished)
def output_request_finished_receiver(sender, logger, **kwargs):
    output_request_logger.info(
        'Output request "%(id)s" to "%(host)s" with path "%(path)s" was successful',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            output_request_id=logger.id,
            output_request_host=logger.data['host'],
            output_request_path=logger.data['path'],
            output_request_method=logger.data['method'],
            output_request_slug=logger.slug,
            output_request_is_secure=logger.data['is_secure'],
            output_request_start=logger.data['start'],
            output_request_stop=logger.data['stop'],
            output_request_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
        )
    )


@receiver(output_request_error)
def output_request_error_receiver(sender, logger, **kwargs):
    output_request_logger.error(
        'Output request "%(id)s" to "%(host)s" with path "%(path)s" failed',
        dict(
            id=logger.id,
            host=logger.data['host'],
            path=logger.data['path'],
        ),
        extra=dict(
            output_request_id=logger.id,
            output_request_host=logger.data['host'],
            output_request_path=logger.data['path'],
            output_request_method=logger.data['method'],
            output_request_slug=logger.slug,
            output_request_is_secure=logger.data['is_secure'],
            output_request_start=logger.data['start'],
            output_request_stop=logger.data['stop'],
            output_request_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
        )
    )


@receiver(command_started)
def command_started_receiver(sender, logger, **kwargs):
    command_logger.info(
        'Command "%(id)s" with name "%(name)s" was started',
        dict(
            id=logger.id,
            name=logger.data['name'],
        ),
        extra=dict(
            command_id=logger.id,
            command_name=logger.data['name'],
            command_is_executed_from_command_line=logger.data['is_executed_from_command_line'],
            command_start=logger.data['start'],
        )
    )


@receiver(command_finished)
def command_finished_receiver(sender, logger, **kwargs):
    command_logger.info(
        'Command "%(id)s" with name "%(name)s" was successful',
        dict(
            id=logger.id,
            name=logger.data['name'],
        ),
        extra=dict(
            command_id=logger.id,
            command_name=logger.data['name'],
            command_is_executed_from_command_line=logger.data['is_executed_from_command_line'],
            command_start=logger.data['start'],
            command_stop=logger.data['stop'],
            command_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
            command_is_error=False
        )
    )


@receiver(command_error)
def command_error_receiver(sender, logger, **kwargs):
    command_logger.error(
        'Command "%(id)s" with name "%(name)s" failed',
        dict(
            id=logger.id,
            name=logger.data['name'],
        ),
        extra=dict(
            command_id=logger.id,
            command_name=logger.data['name'],
            command_is_executed_from_command_line=logger.data['is_executed_from_command_line'],
            command_start=logger.data['start'],
            command_stop=logger.data['stop'],
            command_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
            command_is_error=True
        )
    )


@receiver(celery_task_invocation_triggered)
def celery_task_invocation_triggered_receiver(sender, logger, **kwargs):
    celery_logger.info(
        'Celery task invocation "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" was invoked',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_invocation_task_id=logger.data['celery_task_id'],
            celery_task_invocation_name=logger.data['name'],
            celery_task_invocation_queue=logger.data['queue_name'],
            celery_task_invocation_start=logger.data['start'],
            celery_task_invocation_state='TRIGGERED',
        ),
    )


@receiver(celery_task_invocation_ignored)
def celery_task_invocation_ignored_receiver(sender, logger, **kwargs):
    celery_logger.info(
        'Celery task invocation "%(id)s" with name "%(name)s" was ignored',
        dict(
            id=logger.id,
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_invocation_name=logger.data['name'],
            celery_task_invocation_queue=logger.data['queue_name'],
            celery_task_invocation_start=logger.data['start'],
            celery_task_invocation_stop=logger.data['stop'],
            celery_task_invocation_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
            celery_task_invocation_state='IGNORED',
        ),
    )


@receiver(celery_task_invocation_timeout)
def celery_task_invocation_timeout_receiver(sender, logger, **kwargs):
    celery_logger.warning(
        'Celery task "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" caused a response timeout',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_invocation_task_id=logger.data['celery_task_id'],
            celery_task_invocation_name=logger.data['name'],
            celery_task_invocation_queue=logger.data['queue_name'],
            celery_task_invocation_start=logger.data['start'],
            celery_task_invocation_stop=logger.data['stop'],
            celery_task_invocation_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
            celery_task_invocation_state='TIMEOUT',
        ),
    )


@receiver(celery_task_invocation_expired)
def celery_task_invocation_expired_receiver(sender, logger, **kwargs):
    celery_logger.error(
        'Celery task invocation "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" was expired',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'] or '',
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_invocation_task_id=logger.data['celery_task_id'] or '',
            celery_task_invocation_name=logger.data['name'],
            celery_task_invocation_queue=logger.data['queue_name'],
            celery_task_invocation_start=logger.data['start'],
            celery_task_invocation_stop=logger.data['stop'],
            celery_task_invocation_time=(logger.data['stop'] - logger.data['start']).total_seconds(),
            task_state='EXPIRED',
        ),
    )


@receiver(celery_task_run_started)
def celery_task_run_started_receiver(sender, logger, **kwargs):
    celery_logger.info(
        'Celery task "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" was started',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_name=logger.data['name'],
            celery_task_queue=logger.data['queue_name'],
            celery_task_tart=logger.data['start'],
            celery_task_invocation_state='ACTIVE',
            celery_task_attempt=logger.data['retries'],
        ),
    )


@receiver(celery_task_run_succeeded)
def celery_task_run_succeeded_receiver(sender, logger, **kwargs):
    celery_logger.info(
        'Celery task "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" was successful',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_name=logger.data['name'],
            celery_task_queue=logger.data['queue_name'],
            celery_task_tart=logger.data['start'],
            celery_task_invocation_state='SUCCEEDED',
            celery_task_attempt=logger.data['retries'],
            celery_task_stop=logger.data['stop'],
            celery_task_time=logger.data['stop'] - logger.data['start']
        )
    )


@receiver(celery_task_run_failed)
def celery_task_run_failed_receiver(sender, logger, **kwargs):
    celery_logger.error(
        'Celery task "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" failed',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_name=logger.data['name'],
            celery_task_queue=logger.data['queue_name'],
            celery_task_tart=logger.data['start'],
            celery_task_invocation_state='FAILED',
            celery_task_attempt=logger.data['retries'],
            celery_task_stop=logger.data['stop'],
            celery_task_time=logger.data['stop'] - logger.data['start']
        )
    )


@receiver(celery_task_run_retried)
def celery_task_run_retried_receiver(sender, logger, **kwargs):
    celery_logger.warning(
        'Celery task "%(id)s" with celery id "%(celery_task_id)s" and name "%(name)s" was repeated',
        dict(
            id=logger.id,
            celery_task_id=logger.data['celery_task_id'],
            name=logger.data['name'],
        ),
        extra=dict(
            id=logger.id,
            celery_task_name=logger.data['name'],
            celery_task_queue=logger.data['queue_name'],
            celery_task_tart=logger.data['start'],
            celery_task_invocation_state='RETRIED',
            celery_task_attempt=logger.data['retries'],
            celery_task_stop=logger.data['stop'],
            celery_task_time=logger.data['stop'] - logger.data['start']
        )
    )
