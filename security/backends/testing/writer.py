from attrdict import AttrDict

from django.test.utils import override_settings

from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error,
    output_request_started, output_request_finished, output_request_error,
    command_started, command_output_updated, command_finished, command_error,
    celery_task_invocation_started, celery_task_invocation_triggered, celery_task_invocation_ignored,
    celery_task_invocation_timeout, celery_task_invocation_expired,
    celery_task_run_started, celery_task_run_succeeded, celery_task_run_failed, celery_task_run_retried,
    celery_task_run_output_updated, get_backend_receiver
)

from .app import SecurityTestingBackend


CAPTURED_SIGNALS = {
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


class capture_security_logs(override_settings):

    logged_data = None
    _receivers = None

    def __init__(self, set_testing_writer=False):
        kwargs = {}
        if set_testing_writer:
            kwargs['SECURITY_BACKEND_READER'] = SecurityTestingBackend.backend_name
        super().__init__(**kwargs)

    def _get_receiver(self, signal_name, use_wrapper=False):
        def _log_receiver(sender, logger, signal, **kwargs):
            if use_wrapper:
                logger = CapturedLog(logger)
            capture_security_logs.logged_data[signal_name].append(logger)
        return _log_receiver

    def _set_signal_receiver(self, signal_name, signal, use_wrapper=False):
        receiver = self._get_receiver(signal_name, use_wrapper)
        capture_security_logs._receivers[signal_name] = (receiver, signal)
        capture_security_logs.logged_data[signal_name] = []
        signal.connect(receiver, weak=True)

    def enable(self):
        super().enable()
        capture_security_logs.logged_data = AttrDict()
        capture_security_logs._receivers = {}

        for signal_name, signal in CAPTURED_SIGNALS.items():
            if signal_name.endswith('_started'):
                self._set_signal_receiver(signal_name[0:-8], signal)
            self._set_signal_receiver(signal_name, signal, use_wrapper=True)
        return capture_security_logs.logged_data

    def disable(self):
        for receiver, signal in capture_security_logs._receivers.values():
            signal.disconnect(receiver)
        super().disable()
