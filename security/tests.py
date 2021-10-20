from attrdict import AttrDict

from collections import namedtuple

from contextlib import contextmanager

from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,

    output_request_started, output_request_finished, output_request_error,

    command_started, command_output_updated, command_finished, command_error,

    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,

    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed,
    celery_task_run_retried, celery_task_run_output_updated,
)


all_signals = {
    'input_request_started': input_request_started,
    'input_request_finished': input_request_finished,
    'input_request_error': input_request_error,

    'output_request_started': output_request_started,
    'output_request_finished': output_request_finished,
    'output_request_error': output_request_error,

    'command_started': command_started,
    'command_output_updated': command_output_updated,
    'command_finished': command_finished,
    'command_error': command_error,

    'celery_task_invocation_started': celery_task_invocation_started,
    'celery_task_invocation_triggered': celery_task_invocation_triggered,
    'celery_task_invocation_ignored': celery_task_invocation_ignored,
    'celery_task_invocation_timeout': celery_task_invocation_timeout,
    'celery_task_invocation_expired': celery_task_invocation_expired,

    'celery_task_run_started': celery_task_run_started,
    'celery_task_run_succeeded': celery_task_run_succeeded,
    'celery_task_run_failed': celery_task_run_failed,
    'celery_task_run_retried': celery_task_run_retried,
    'celery_task_run_output_updated': celery_task_run_output_updated,
}


class CapturedLog:

    def __init__(self, logger):
        self.id = logger.id
        self.slug = logger.slug
        self.data = dict(logger.data)
        self.related_objects = list(logger.related_objects)
        self.extra_data = dict(logger.extra_data)
        self.logger = logger


@contextmanager
def capture_security_logs():
    logged_data = AttrDict(
        input_request=[],
        output_request=[],
        celery_task_invocation=[],
        celery_task_run=[],
        command=[],
    )

    def log_started_receiver(sender, logger, **kwargs):
        logged_data[logger.name.replace('-', '_')].append(logger)

    def log_receiver(sender, logger, signal, **kwargs):
        logged_data[signal.name].append(CapturedLog(logger))

    try:
        for signal in [celery_task_invocation_started, celery_task_run_started, command_started, input_request_started,
                       output_request_started]:
            signal.connect(log_started_receiver, weak=True)

        for signal_name, signal in all_signals.items():
            signal.name = signal_name
            logged_data[signal_name] = []
            signal.connect(log_receiver, weak=True)

        yield logged_data
    finally:
        for signal in [celery_task_invocation_started, celery_task_run_started, command_started, input_request_started,
                       output_request_started]:
            signal.disconnect(log_started_receiver)

        for signal in all_signals.values():
            del signal.name
            signal.disconnect(log_receiver)
