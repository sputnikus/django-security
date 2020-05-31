import os
import base64
import logging
import pickle

import uuid

from datetime import timedelta

from django.conf import settings as django_settings
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import OutputWrapper
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache
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

from .decorators import atomic_log
from .config import settings
from .models import CeleryTaskRunLog, CeleryTaskLog, CeleryTaskLogState, CeleryTaskRunLogState
from .utils import LogStringIO


logger = logging.getLogger(__name__)


def default_unique_key_generator(task, task_args, task_kwargs):
    unique_key = [task.name]
    if task_args:
        unique_key += [str(v) for v in task_args]
    if task_kwargs:
        unique_key += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]
    return '||'.join(unique_key)


class LoggedTask(Task):
    abstract = True

    _log_messages = {
        'expire': 'Task "%(task_name)s" (%(task)s) is expired',
        'failure': 'Task "%(task_name)s" (%(task)s) is failed',
        'retry': 'Task "%(task_name)s" (%(task)s) is retried',
        'success': 'Task "%(task_name)s" (%(task)s) is completed',
        'apply': 'Task "%(task_name)s" (%(task)s) is applied',
        'start': 'Task "%(task_name)s" (%(task)s) is running',
    }

    stale_time_limit = None
    # Support set retry delay in list. Retry countdown value is get from list where index is attempt
    # number (request.retries)
    default_retry_delays = None
    # Unique task if task with same input already exists no extra task is created and old task result is returned
    unique = False
    unique_key_generator = default_unique_key_generator
    _stackprotected = True

    def _get_log_message(self, log_name):
        return self._log_messages[log_name]

    def _get_unique_key(self, task_args, task_kwargs):
        return (
            str(uuid.uuid5(uuid.NAMESPACE_DNS, self.unique_key_generator(task_args, task_kwargs)))
            if self.unique else None
        )

    def _clear_unique_key(self, task_args, task_kwargs):
        unique_key = self._get_unique_key(task_args, task_kwargs)
        if unique_key:
            cache.delete(unique_key)

    def _get_unique_task_id(self, task_id, task_args, task_kwargs, stale_time_limit):
        unique_key = self._get_unique_key(task_args, task_kwargs)

        if unique_key and not stale_time_limit:
            raise CeleryError('For unique tasks is require set task stale_time_limit')

        if unique_key and not self._get_app().conf.task_always_eager:
            if cache.add(unique_key, task_id, stale_time_limit):
                return task_id
            else:
                unique_task_id = cache.get(unique_key)
                return (
                    unique_task_id if unique_task_id
                    else self._get_unique_task_id(task_id, task_args, task_kwargs, stale_time_limit)
                )
        else:
            return task_id

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

    def __call__(self, *args, **kwargs):
        """
        Overrides parent which works with thread stack. We didn't want to allow change context which was generated in
        one of apply methods. Call task directly is now disallowed.
        """
        req = self.request_stack.top

        if not req or req.called_directly:
            raise CeleryError(
                'Task cannot be called directly. Please use apply, apply_async or apply_async_on_commit methods'
            )

        if req._protected:
            raise CeleryError('Request is protected')
        # request is protected (no usage in celery but get from function _install_stack_protection in
        # celery library)
        req._protected = 1

        celery_task_run_log = self._create_task_run_log(args, kwargs)
        # Every set attr is sent here
        self.request.celery_task_run_log = celery_task_run_log
        self.request.output_stream = LogStringIO(post_write_callback=self._store_log_output)
        self.on_start_task(self.task_run_log, args, kwargs)
        with atomic_log(celery_task_run_log=celery_task_run_log):
            return self.run(*args, **kwargs)

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
                task_queue=task_log.queue_name,
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
                task_queue=task_log.queue_name,
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
                task_queue=task_log.queue_name,
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

        self._clear_unique_key(args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
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
                task_queue=task_log.queue_name,
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

        self._clear_unique_key(args, kwargs)

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
        try:
            self.on_failure_task(self.task_run_log, args, kwargs, exc)
        except CeleryTaskRunLog.DoesNotExist:
            pass

    def _compute_eta(self, eta, countdown, apply_time):
        if countdown is not None:
            return apply_time + timedelta(seconds=countdown)
        elif eta:
            return eta
        else:
            return apply_time

    def _compute_expires(self, expires, time_limit, stale_time_limit, apply_time):
        expires = self.expires if expires is None else expires
        if expires is not None:
            return apply_time + timedelta(seconds=expires) if isinstance(expires, int) else expires
        elif self._get_stale_time_limit(stale_time_limit) is not None and time_limit is not None:
            return apply_time + timedelta(seconds=stale_time_limit - time_limit)
        else:
            return None

    def _get_time_limit(self, time_limit):
        if time_limit is not None:
            return time_limit
        elif self.soft_time_limit is not None:
            return self.soft_time_limit
        else:
            return self._get_app().conf.task_time_limit

    def _get_stale_time_limit(self, stale_time_limit):
        if stale_time_limit is not None:
            return stale_time_limit
        elif self.stale_time_limit is not None:
            return self.stale_time_limit
        elif hasattr(django_settings, 'CELERYD_TASK_STALE_TIME_LIMIT'):
            return django_settings.CELERYD_TASK_STALE_TIME_LIMIT
        else:
            return None

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
        if related_objects:
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
            start=now()
        )

    def _first_apply(self, is_async, args=None, kwargs=None, related_objects=None, task_id=None, eta=None,
                     countdown=None, expires=None, time_limit=None, stale_time_limit=None, **options):
        task_id = task_id or task_uuid()
        apply_time = now()
        time_limit = self._get_time_limit(time_limit)
        eta = self._compute_eta(eta, countdown, apply_time)
        countdown = None
        queue = str(options.get('queue', getattr(self, 'queue', self._get_app().conf.task_default_queue)))
        stale_time_limit = self._get_stale_time_limit(stale_time_limit)
        expires = self._compute_expires(expires, time_limit, stale_time_limit, apply_time)

        options.update(dict(
            time_limit=time_limit,
            eta=eta,
            countdown=countdown,
            queue=queue,
            expires=expires,
        ))
        unique_task_id = self._get_unique_task_id(task_id, args, kwargs, stale_time_limit)
        if is_async and unique_task_id != task_id:
            return AsyncResult(unique_task_id, app=self._get_app())

        task_initiation = self._create_task_log(
            task_id, args, kwargs, apply_time, eta, expires, stale_time_limit, queue, related_objects
        )
        self.on_apply_task(task_initiation, args, kwargs, options)
        if is_async:
            return super().apply_async(task_id=task_id, args=args, kwargs=kwargs, **options)
        else:
            return super().apply(task_id=task_id, args=args, kwargs=kwargs, **options)

    def apply_async_on_commit(self, args=None, kwargs=None, related_objects=None, **options):
        app = self._get_app()
        if app.conf.task_always_eager:
            self.apply_async(args=args, kwargs=kwargs, related_objects=related_objects, **options)
        else:
            self_inst = self
            transaction.on_commit(
                lambda: self_inst.apply_async(args=args, kwargs=kwargs, related_objects=related_objects, **options)
            )

    def apply(self, args=None, kwargs=None, related_objects=None, **options):
        if self.request.id:
            return super().apply(args=args, kwargs=kwargs, **options)
        else:
            return self._first_apply(
                is_async=False, args=args, kwargs=kwargs, related_objects=related_objects, **options
            )

    def apply_async(self, args=None, kwargs=None, related_objects=None, **options):
        app = self._get_app()
        try:
            if self.request.id or app.conf.task_always_eager:
                return super().apply_async(args=args, kwargs=kwargs, related_objects=related_objects, **options)
            else:
                return self._first_apply(
                    is_async=True, args=args, kwargs=kwargs, related_objects=related_objects, **options,
                )
        except (InterfaceError, OperationalError) as ex:
            logger.warn('Closing old database connections, following exception thrown: %s', str(ex))
            close_old_connections()
            raise ex

    def delay_on_commit(self, *args, **kwargs):
        self.apply_async_on_commit(args, kwargs)

    def retry(self, args=None, kwargs=None, exc=None, throw=True,
              eta=None, countdown=None, max_retries=None, default_retry_delays=None, **options):
        if (default_retry_delays or (
                max_retries is None and eta is None and countdown is None and max_retries is None
                and self.default_retry_delays)):
            default_retry_delays = self.default_retry_delays if default_retry_delays is None else default_retry_delays
            max_retries = len(default_retry_delays)
            countdown = default_retry_delays[self.request.retries] if self.request.retries < max_retries else None

        if not eta and countdown is None:
            countdown = self.default_retry_delay

        if not eta:
            eta = now() + timedelta(seconds=countdown)

        self.on_retry_task(self.task_run_log, args, kwargs, exc, eta)

        # Celery retry not working in eager mode. This simple hack fix it.
        self.request.is_eager = False
        return super().retry(
            args=args, kwargs=kwargs, exc=exc, throw=throw,
            eta=eta, max_retries=max_retries, **options
        )

    def apply_async_and_get_result(self, args=None, kwargs=None, timeout=None, propagate=True, related_objects=None,
                                   **options):
        """
        Apply task in an asynchronous way, wait defined timeout and get AsyncResult or TimeoutError
        :param args: task args
        :param kwargs: task kwargs
        :param timeout: timout in seconds to wait for result
        :param propagate: propagate or not exceptions from celery task
        :param options: apply_async method options
        :return: AsyncResult or TimeoutError
        """
        result = self.apply_async(args=args, kwargs=kwargs, related_objects=related_objects, **options)
        if timeout is None or timeout > 0:
            return result.get(timeout=timeout, propagate=propagate)
        else:
            raise TimeoutError('The operation timed out.')

    def is_processing(self, related_objects=None):
        return CeleryTaskLog.objects.filter_processing(
            name=self.name,
            related_objects=related_objects
        ).exists()


def obj_to_string(obj):
    return base64.encodebytes(pickle.dumps(obj)).decode('utf8')


def string_to_obj(obj_string):
    return pickle.loads(base64.decodebytes(obj_string.encode('utf8')))


def get_django_command_task(command_name):
    if command_name not in current_app.tasks:
        raise ImproperlyConfigured('Command was not found please check AUTO_GENERATE_TASKS_FOR_DJANGO_COMMANDS setting')
    return current_app.tasks[command_name]


for name in get_commands():
    if name in settings.AUTO_GENERATE_TASKS_FOR_DJANGO_COMMANDS:
        def generate_command_task(command_name):
            shared_task_kwargs = dict(
                base=LoggedTask,
                bind=True,
                name=command_name,
                ignore_result=True
            )
            shared_task_kwargs.update(settings.AUTO_GENERATE_TASKS_FOR_DJANGO_COMMANDS[command_name])

            @shared_task(
                **shared_task_kwargs
            )
            def command_task(self, command_args=None, **kwargs):
                command_args = [] if command_args is None else command_args
                call_command(
                    command_name,
                    settings=os.environ.get('DJANGO_SETTINGS_MODULE'),
                    *command_args,
                    stdout=self.request.output_stream,
                    stderr=self.request.output_stream,
                    **kwargs
                )

        generate_command_task(name)
