import os
import base64
import logging
import pickle

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
except ImportError:
    raise ImproperlyConfigured('Missing celery library, please install it')

from django_celery_extensions.task import DjangoTask

from .decorators import atomic_log
from .config import settings
from .models import CeleryTaskRunLog, CeleryTaskLog, CeleryTaskLogState, CeleryTaskRunLogState
from .utils import LogStringIO, log_context_manager


logger = logging.getLogger(settings.TASK_LOGGER_NAME)


class LoggedTask(DjangoTask):

    abstract = True

    _log_messages = {
        'expire': 'Task "%(task_name)s" (%(task)s) is expired',
        'failure': 'Task "%(task_name)s" (%(task)s) is failed',
        'retry': 'Task "%(task_name)s" (%(task)s) is retried',
        'success': 'Task "%(task_name)s" (%(task)s) is completed',
        'apply': 'Task "%(task_name)s" (%(task)s) is applied',
        'start': 'Task "%(task_name)s" (%(task)s) is running',
    }

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
        return self.request.celery_task_run_log

    @property
    def task_log(self):
        return self.request.celery_task_log

    def on_start(self, args, kwargs):
        super().on_start(args, kwargs)
        celery_task_run_log = self._create_task_run_log(args, kwargs)
        # Every set attr is sent here
        self.request.celery_task_run_log = celery_task_run_log
        self.request.output_stream = LogStringIO(post_write_callback=self._store_log_output)
        self.on_start_task(self.task_run_log, args, kwargs)

    def _start(self, *args, **kwargs):
        with atomic_log(celery_task_run_log=self.request.celery_task_run_log):
            return super()._start(*args, **kwargs)

    def on_apply(self, task_id, apply_time, stale_time_limit, args, kwargs, options):
        super().on_apply(task_id, apply_time, stale_time_limit, args, kwargs, options)
        task_initiation = self._create_task_log(
            task_id,
            args,
            kwargs,
            apply_time,
            options.get('eta'),
            options.get('expires'),
            stale_time_limit,
            options.get('queue'),
            options.pop('related_objects', None)
        )
        self.on_apply_task(task_initiation, args, kwargs, options)

    def on_apply_task(self, task_log, args, kwargs, options):
        """
        On apply task is invoked before task was prepared. Therefore task request context is not prepared.
        :param task_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param options: input task options
        """
        logger.info(
            self._get_log_message('apply'),
            dict(
                task=task_log.celery_task_id,
                task_name=task_log.name,
                **(kwargs or {})
            ),
            extra=dict(
                task_args=args,
                task_id=task_log.celery_task_id,
                task_input=task_log.input,
                task_kwargs=kwargs,
                task_log_id=task_log.pk,
                task_name=task_log.name,
                task_queue=task_log.queue_name,
                task_state=task_log.state.name,
            ),
        )

    def on_apply_retry(self, args, kwargs, exc, eta):
        super().on_apply_retry(args, kwargs, exc, eta)
        self.on_retry_task(self.task_run_log, args, kwargs, exc, eta)

    def on_retry_task(self, task_run_log, args, kwargs, exc, eta):
        """
        On retry task is invoked before task was retried.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param exc: raised exception which caused retry
        """
        task_log = task_run_log.get_task_log()
        logger.warning(
            self._get_log_message('retry'),
            dict(
                attempt=self.request.retries,
                exception=str(exc),
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                **(kwargs or {})
            ),
            extra=dict(
                task_args=args,
                task_exception=str(exc),
                task_id=task_run_log.celery_task_id,
                task_kwargs=kwargs,
                task_log_id=None if not task_log else task_log.pk,
                task_name=task_run_log.name,
                task_queue=None if not task_log else task_log.queue_name,
                task_retries=self.request.retries,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
            )
        )
        stop = now()
        task_run_log.change_and_save(
            state=CeleryTaskLogState.RETRIED,
            error_message=str(exc),
            stop=stop,
            time=(stop - task_run_log.start).total_seconds(),
            output=self.request.output_stream.getvalue(),
            estimated_time_of_next_retry=eta
        )
        task_log = task_run_log.get_task_log()
        if task_log:
            task_log.change_and_save(
                state=CeleryTaskLogState.RETRIED
            )

    def on_start_task(self, task_run_log, args, kwargs):
        """
        On start task is invoked during task started.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        """
        task_log = task_run_log.get_task_log()
        logger.info(
            self._get_log_message('start'),
            dict(
                attempt=self.request.retries,
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                **(kwargs or {})
            ),
            extra=dict(
                task_args=args,
                task_id=task_run_log.celery_task_id,
                task_kwargs=kwargs,
                task_log_id=None if not task_log else task_log.pk,
                task_name=task_run_log.name,
                task_queue=None if not task_log else task_log.queue_name,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
            )
        )
        if task_log:
            task_log.change_and_save(
                state=CeleryTaskLogState.ACTIVE
            )

    def on_success_task(self, task_run_log, args, kwargs, retval):
        """
        On start task is invoked if task is successful.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param retval: return value of a task
        """
        task_log = task_run_log.get_task_log()
        logger.info(
            self._get_log_message('success'),
            dict(
                attempt=self.request.retries,
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                **(kwargs or {})
            ),
            extra=dict(
                task_args=args,
                task_duration=task_run_log.time,
                task_empty_error=task_run_log.error_message is None or len(task_run_log.error_message) < 1,
                task_empty_output=task_run_log.output is None or len(task_run_log.output) < 1,
                task_id=task_run_log.celery_task_id,
                task_kwargs=kwargs,
                task_log_id=None if not task_log else task_log.pk,
                task_name=task_run_log.name,
                task_queue=None if not task_log else task_log.queue_name,
                task_retries=task_run_log.retries,
                task_retval=retval,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
            )
        )

        if retval:
            self.request.output_stream.write('Return value is "{}"'.format(retval))

        stop = now()
        task_run_log.change_and_save(
            state=CeleryTaskRunLogState.SUCCEEDED,
            stop=stop,
            time=(stop - task_run_log.start).total_seconds(),
            result=retval,
            output=self.request.output_stream.getvalue()
        )

        if task_log:
            task_log.change_and_save(
                state=CeleryTaskLogState.SUCCEEDED
            )

    def on_success(self, retval, task_id, args, kwargs):
        super().on_success(retval, task_id, args, kwargs)
        self.on_success_task(self.task_run_log, args, kwargs, retval)

    def on_failure_task(self, task_run_log, args, kwargs, exc):
        """
        On failure task is invoked if task end with some exception.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param exc: raised exception which caused retry
        """
        task_log = task_run_log.get_task_log()
        logger.error(
            self._get_log_message('failure'),
            dict(
                attempt=self.request.retries,
                exception=str(exc),
                task=task_run_log.celery_task_id,
                task_name=task_run_log.name,
                **(kwargs or {})
            ),
            extra=dict(
                task_args=args,
                task_duration=task_run_log.time,
                task_empty_error=task_run_log.error_message is None or len(task_run_log.error_message) < 1,
                task_empty_output=task_run_log.output is None or len(task_run_log.output) < 1,
                task_exception=str(exc),
                task_id=task_run_log.celery_task_id,
                task_kwargs=kwargs,
                task_log_id=None if not task_log else task_log.pk,
                task_name=task_run_log.name,
                task_queue=None if not task_log else task_log.queue_name,
                task_retries=task_run_log.retries,
                task_run_log_id=task_run_log.pk,
                task_started_at=task_run_log.start,
                task_state=task_run_log.state.name,
            )
        )
        stop = now()
        task_run_log.change_and_save(
            state=CeleryTaskRunLogState.FAILED,
            stop=stop,
            time=(stop - task_run_log.start).total_seconds(),
            error_message=str(exc),
            output=self.request.output_stream.getvalue()
        )
        if task_log:
            task_log.change_and_save(
                state=CeleryTaskLogState.FAILED
            )

    def expire_task(self, task_log):
        logger.error(
            self._get_log_message('expire'),
            dict(
                task=task_log.celery_task_id,
                task_name=task_log.name
            ),
            extra=dict(
                task_expired_at=task_log.stale,
                task_id=task_log.celery_task_id,
                task_input=task_log.input,
                task_log_id=task_log.pk,
                task_name=task_log.name,
                task_queue=task_log.queue_name,
                task_state=task_log.state.name,
            )
        )
        task_log.change_and_save(
            state=CeleryTaskLogState.EXPIRED
        )
        task_log.runs.filter(
            state=CeleryTaskRunLogState.ACTIVE
        ).update(
            state=CeleryTaskRunLogState.EXPIRED
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        super().on_failure(exc, task_id, args, kwargs, einfo)
        try:
            self.on_failure_task(self.task_run_log, args, kwargs, exc)
        except CeleryTaskRunLog.DoesNotExist:
            pass

    def _create_task_log(self, task_id, task_args, task_kwargs, apply_time, eta, expires, stale_time_limit,
                         queue, related_objects):
        task_input = []
        if task_args:
            task_input += [str(v) for v in task_args]
        if task_kwargs:
            task_input += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]

        celery_task_log = CeleryTaskLog.objects.create(
            celery_task_id=task_id,
            name=self.name,
            queue_name=queue,
            input=', '.join(task_input),
            task_args=task_args,
            task_kwargs=task_kwargs,
            estimated_time_of_first_arrival=eta,
            expires=expires,
            stale=apply_time + timedelta(seconds=stale_time_limit) if stale_time_limit is not None else None
        )
        related_objects = [] if related_objects is None else list(related_objects)
        if log_context_manager.is_active():
            related_objects += log_context_manager.get_logs()

        celery_task_log.related_objects.add(*related_objects)
        return celery_task_log

    def _create_task_run_log(self, task_args, task_kwargs):
        return CeleryTaskRunLog.objects.create(
            celery_task_id=self.request.id,
            name=self.name,
            task_args=task_args,
            task_kwargs=task_kwargs,
            retries=self.request.retries,
            state=CeleryTaskRunLogState.ACTIVE,
            start=now(),
        )

    def is_processing(self, related_objects=None):
        return CeleryTaskLog.objects.filter_processing(
            name=self.name,
            related_objects=related_objects
        ).exists()

    def get_command_kwargs(self):
        return dict(
            stdout=self.request.output_stream,
            stderr=self.request.output_stream,
        )
