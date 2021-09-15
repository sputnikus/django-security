from django.dispatch import Signal, receiver

from security.config import settings


def get_backend_receiver(backend_name):
    def backend_receiver(signal):
        def _decorator(func):
            def _wrapper(*args, **kwargs):
                if settings.BACKENDS is None or backend_name in settings.BACKENDS:
                    func(*args, **kwargs)
            signal.connect(_wrapper, weak=False)
            return func
        return _decorator
    return backend_receiver


input_request_started = Signal()
input_request_finished = Signal()
input_request_error = Signal()

output_request_started = Signal()
output_request_finished = Signal()
output_request_error = Signal()

command_started = Signal()
command_output_updated = Signal()
command_finished = Signal()
command_error = Signal()

celery_task_invocation_started = Signal()
celery_task_invocation_triggered = Signal()
celery_task_invocation_ignored = Signal()
celery_task_invocation_timeout = Signal()
celery_task_invocation_expired = Signal()

celery_task_run_started = Signal()
celery_task_run_succeeded = Signal()
celery_task_run_failed = Signal()
celery_task_run_retried = Signal()
celery_task_run_output_updated = Signal()
