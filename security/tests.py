from attrdict import AttrDict

from contextlib import contextmanager

from security.backends.signals import (
    celery_task_invocation_started, celery_task_run_started, command_started, input_request_started,
    output_request_started
)


@contextmanager
def capture_security_logs():
    logged_data = AttrDict(
        input_request=[],
        output_request=[],
        celery_task_invocation=[],
        celery_task_run=[],
        command=[],
    )

    def log_receiver(sender, logger, **kwargs):
        logged_data[logger.name.replace('-', '_')].append(logger)

    try:
        celery_task_invocation_started.connect(log_receiver)
        celery_task_run_started.connect(log_receiver)
        command_started.connect(log_receiver)
        input_request_started.connect(log_receiver)
        output_request_started.connect(log_receiver)
        yield logged_data
    finally:
        celery_task_invocation_started.disconnect(log_receiver)
        celery_task_run_started.disconnect(log_receiver)
        command_started.disconnect(log_receiver)
        input_request_started.disconnect(log_receiver)
        output_request_started.disconnect(log_receiver)
