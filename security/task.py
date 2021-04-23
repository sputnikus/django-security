import os
import base64
import logging
import pickle
import warnings

from datetime import timedelta

from distutils.version import StrictVersion

from django.conf import settings as django_settings
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import OutputWrapper
from django.core.exceptions import ImproperlyConfigured
from django.db import close_old_connections, transaction
from django.db.utils import InterfaceError, OperationalError
from django.utils.timezone import now

try:
    from celery import Task, shared_task, current_app
    from celery.result import AsyncResult
    from celery.exceptions import CeleryError, TimeoutError
    from celery.worker.request import Request
    from kombu.utils import uuid as task_uuid
except ImportError:
    raise ImproperlyConfigured('Missing celery library, please install it')

from django_celery_extensions.task import DjangoTask

from chamber.utils.transaction import on_success, in_atomic_block

from .decorators import atomic_log
from .config import settings
from .models import CeleryTaskRunLog, CeleryTaskInvocationLog, CeleryTaskInvocationLogState, CeleryTaskRunLogState
from .utils import LogStringIO, log_context_manager


logger = logging.getLogger(settings.TASK_LOGGER_NAME)


class LoggedTask(DjangoTask):

    abstract = True

    _log_messages = {
        'expire': 'Task "%(task_name)s" (%(task)s) is expired',
        'failure': 'Task "%(task_name)s" (%(task)s) is failed',
        'retry': 'Task "%(task_name)s" (%(task)s) is retried',
        'success': 'Task "%(task_name)s" (%(task)s) is completed',
        'trigger': 'Task "%(task_name)s" (%(task)s) is applied',
        'start': 'Task "%(task_name)s" (%(task)s) is running',
    }

    def _create_invocation_log(self, invocation_id, task_args, task_kwargs, apply_time, queue, is_async, is_unique,
                               is_on_commit, related_objects):
        task_input = []
        if task_args:
            task_input += [str(v) for v in task_args]
        if task_kwargs:
            task_input += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]

        celery_task_log = CeleryTaskInvocationLog.objects.create(
            invocation_id=invocation_id,
            name=self.name,
            queue_name=queue,
            input=', '.join(task_input),
            task_args=task_args,
            task_kwargs=task_kwargs,
            applied_at=apply_time,
            is_async=is_async,
            is_unique=is_unique,
            is_on_commit=is_on_commit,
            is_duplicate=False
        )
        related_objects = [] if related_objects is None else list(related_objects)
        if log_context_manager.is_active():
            related_objects += log_context_manager.get_logs()
        celery_task_log.related_objects.add(*related_objects)
        return celery_task_log

    def _update_invocation_log(self, invocation_id, trigger_time, is_duplicate, eta, expires, stale_time_limit,
                               task_id):
        celery_task_log = CeleryTaskInvocationLog.objects.get(invocation_id=invocation_id)
        return celery_task_log.change_and_save(
            estimated_time_of_first_arrival=eta,
            expires_at=expires,
            triggered_at=trigger_time,
            stale_at=trigger_time + timedelta(seconds=stale_time_limit) if stale_time_limit is not None else None,
            is_duplicate=is_duplicate,
            state=CeleryTaskInvocationLogState.TRIGGERED,
            celery_task_id=task_id
        )

    def on_invocation_apply_log(self, invocation_log):
        pass

    def on_invocation_apply(self, invocation_id, args, kwargs, options):
        super().on_invocation_apply(invocation_id, args, kwargs, options)

        is_on_commit = options.get('is_on_commit')

        self_inst = self
        def _on_invocation_apply_log():
            invocation_log = self_inst._create_invocation_log(
                invocation_id,
                args,
                kwargs,
                apply_time=options.get('apply_time'),
                queue=options.get('queue'),
                is_async=options.get('is_async'),
                is_unique=self.unique,
                is_on_commit=is_on_commit,
                related_objects=options.pop('related_objects', None),
            )
            self_inst.on_invocation_apply_log(invocation_log)

        if is_on_commit and in_atomic_block():
            if settings.TASK_USE_ON_SUCCESS:
                on_success(_on_invocation_apply_log, using=options.get('using'))
            else:
                transaction.on_commit(_on_invocation_apply_log, using=options.get('using'))
        else:
            _on_invocation_apply_log()

    def on_invocation_trigger_log(self, invocation_log):
        logger.info(
            self._get_log_message('trigger'),
            dict(
                task=invocation_log.celery_task_id,
                task_name=invocation_log.name
            ),
            extra=dict(
                invocation_id=invocation_log.id,
                task_id=invocation_log.celery_task_id,
                task_name=invocation_log.name,
                task_queue=invocation_log.queue_name,
                task_state=invocation_log.state.name,
            ),
        )

    def on_invocation_trigger(self, invocation_id, args, kwargs, task_id, options):
        super().on_invocation_trigger(invocation_id, args, kwargs, task_id, options)

        invocation_log = self._update_invocation_log(
            invocation_id,
            trigger_time=options.get('trigger_time'),
            is_duplicate=False,
            eta=options.get('eta'),
            expires=options.get('expires'),
            stale_time_limit=options.get('stale_time_limit'),
            task_id=task_id
        )
        self.on_invocation_trigger_log(invocation_log)

    def on_invocation_unique_log(self, invocation_log):
        pass

    def on_invocation_unique(self, invocation_id, args, kwargs, task_id, options):
        super().on_invocation_unique(invocation_id, args, kwargs, task_id, options)

        invocation_log = self._update_or_create_invocation_log(
            invocation_id,
            trigger_time=options.get('trigger_time'),
            is_duplicate=True,
            eta=options.get('eta'),
            expires=options.get('expires'),
            stale_time_limit=options.get('stale_time_limit'),
            task_id=task_id
        )
        self.on_invocation_unique_log(invocation_log)

    def on_invocation_timeout_log(self, invocation_log):
        pass

    def on_invocation_timeout(self, invocation_id, args, kwargs, task_id, ex, options):
        super().on_invocation_timeout(invocation_id, args, kwargs, task_id, ex, options)
        invocation_log = CeleryTaskInvocationLog.objects.get(invocation_id=invocation_id).change_and_save(
            state=CeleryTaskInvocationLogState.TIMEOUT
        )
        self.on_invocation_timeout_log(invocation_log)

    def _create_task_run_log(self, task_id, task_args, task_kwargs):
        return CeleryTaskRunLog.objects.create(
            celery_task_id=task_id,
            queue_name=self.request.delivery_info.get('routing_key'),
            name=self.name,
            task_args=task_args,
            task_kwargs=task_kwargs,
            retries=self.request.retries,
            state=CeleryTaskRunLogState.ACTIVE,
            start=now(),
        )

    def on_task_start_log(self, task_run_log):
        """
        On start task is invoked during task started.
        """
        logger.info(
            self._get_log_message('start'),
            dict(
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name
            ),
            extra=dict(
                task_id=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                task_queue=task_run_log.queue_name,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
                task_attempt=self.request.retries,
            )
        )

    def on_task_start(self, task_id, args, kwargs):
        super().on_task_start(task_id, args, kwargs)
        task_run_log = self._create_task_run_log(task_id, args, kwargs)
        task_run_log.get_task_invocation_logs().filter(
            state__in={CeleryTaskInvocationLogState.WAITING, CeleryTaskInvocationLogState.TRIGGERED}
        ).change_and_save(
            state=CeleryTaskInvocationLogState.ACTIVE
        )
        # Every set attr is sent here
        self.request.celery_task_run_log = task_run_log
        self.request.output_stream = LogStringIO(flush_callback=self._store_log_output)
        self.on_task_start_log(task_run_log)

    def on_task_retry_log(self, task_run_log, exc, eta):
        """
        On retry task is invoked before task was retried.
        :param task_run_log: logged celery task instance
        :param exc: raised exception which caused retry
        """
        logger.warning(
            self._get_log_message('retry'),
            dict(
                exception=str(exc),
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name
            ),
            extra=dict(
                task_exception=str(exc),
                task_id=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                task_queue=task_run_log.queue_name,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
                task_attempt=self.request.retries,
                task_duration=task_run_log.time,
                task_empty_error=task_run_log.error_message is None or len(task_run_log.error_message) < 1,
                task_empty_output=task_run_log.output is None or len(task_run_log.output) < 1,
            )
        )

    def on_task_retry(self, task_id, args, kwargs, exc, eta):
        super().on_task_retry(task_id,args, kwargs, exc, eta)
        stop = now()
        self.task_run_log.change_and_save(
            state=CeleryTaskRunLogState.RETRIED,
            error_message=str(exc),
            stop=stop,
            time=(stop - self.task_run_log.start).total_seconds(),
            output=self.request.output_stream.getvalue(),
            estimated_time_of_next_retry=eta
        )
        self.on_task_retry_log(self.task_run_log, exc, eta)

    def on_task_failure_log(self, task_run_log, exc):
        """
        On failure task is invoked if task end with some exception.
        :param task_run_log: logged celery task instance
        :param exc: raised exception which caused retry
        """
        logger.error(
            self._get_log_message('failure'),
            dict(
                exception=str(exc),
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name
            ),
            extra=dict(
                task_exception=str(exc),
                task_id=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                task_queue=task_run_log.queue_name,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
                task_attempt=self.request.retries,
                task_duration=task_run_log.time,
                task_empty_error=task_run_log.error_message is None or len(task_run_log.error_message) < 1,
                task_empty_output=task_run_log.output is None or len(task_run_log.output) < 1,
            )
        )

    def on_task_failure(self, task_id, args, kwargs, exc, einfo):
        super().on_task_failure(task_id, args, kwargs, exc, einfo)
        try:
            stop = now()
            self.task_run_log.change_and_save(
                state=CeleryTaskRunLogState.FAILED,
                stop=stop,
                time=(stop - self.task_run_log.start).total_seconds(),
                error_message=str(exc),
                output=self.request.output_stream.getvalue()
            )
            self.task_run_log.get_task_invocation_logs().filter(state__in={
                CeleryTaskInvocationLogState.WAITING,
                CeleryTaskInvocationLogState.TRIGGERED,
                CeleryTaskInvocationLogState.ACTIVE
            }).change_and_save(
                state=CeleryTaskInvocationLogState.FAILED
            )
            self.on_task_failure_log(self.task_run_log, exc)
        except CeleryTaskRunLog.DoesNotExist:
            pass

    def on_task_success_log(self, task_run_log, retval):
        """
        On start task is invoked if task is successful.
        :param task_run_log: logged celery task instance
        :param retval: return value of a task
        """
        logger.error(
            self._get_log_message('success'),
            dict(
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name
            ),
            extra=dict(
                task_id=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                task_queue=task_run_log.queue_name,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
                task_attempt=self.request.retries,
                task_duration=task_run_log.time,
                task_empty_output=task_run_log.output is None or len(task_run_log.output) < 1,
            )
        )

    def on_task_success(self, task_id, args, kwargs, retval):
        super().on_task_success(task_id, args, kwargs, retval)

        stop = now()
        self.task_run_log.change_and_save(
            state=CeleryTaskRunLogState.SUCCEEDED,
            stop=stop,
            time=(stop - self.task_run_log.start).total_seconds(),
            result=retval,
            output=self.request.output_stream.getvalue()
        )
        self.task_run_log.get_task_invocation_logs().filter(state__in={
            CeleryTaskInvocationLogState.WAITING,
            CeleryTaskInvocationLogState.TRIGGERED,
            CeleryTaskInvocationLogState.ACTIVE
        }).change_and_save(
            state=CeleryTaskInvocationLogState.SUCCEEDED
        )
        self.on_task_success_log(self.task_run_log, retval)

    def expire_invocation(self, invocation_log):
        invocation_log.change_and_save(
            state=CeleryTaskInvocationLogState.EXPIRED
        )
        invocation_log.runs.filter(
            state=CeleryTaskRunLogState.ACTIVE
        ).update(
            state=CeleryTaskRunLogState.EXPIRED
        )
        logger.error(
            self._get_log_message('expire'),
            dict(
                task=invocation_log.celery_task_id,
                task_name=invocation_log.name
            ),
            extra=dict(
                task_expired_at=now(),
                task_id=invocation_log.celery_task_id,
                task_input=invocation_log.input,
                task_log_id=invocation_log.pk,
                task_name=invocation_log.name,
                task_queue=invocation_log.queue_name,
                task_state=invocation_log.state.name,
            )
        )

    def _get_log_message(self, log_name):
        return self._log_messages[log_name]

    def _store_log_output(self, output_stream):
        self.request.celery_task_run_log.change_and_save(
            output=output_stream.getvalue(),
            update_only_changed_fields=True
        )

    @property
    def stdout(self):
        return OutputWrapper(self.request.output_stream)

    @property
    def stderr(self):
        return OutputWrapper(self.request.output_stream)

    @property
    def task_run_log(self):
        try:
            return self.request.celery_task_run_log
        except AttributeError:
            raise CeleryTaskRunLog.DoesNotExist()

    @property
    def task_log(self):
        return self.request.celery_task_log

    def _start(self, *args, **kwargs):
        with atomic_log(celery_task_run_log=self.request.celery_task_run_log):
            return super()._start(*args, **kwargs)

    def is_processing(self, related_objects=None):
        return CeleryTaskInvocationLog.objects.filter_processing(
            name=self.name,
            related_objects=related_objects
        ).exists()

    def get_command_kwargs(self):
        return dict(
            stdout=self.request.output_stream,
            stderr=self.request.output_stream,
        )
