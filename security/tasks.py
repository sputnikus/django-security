import os
import base64
import logging
import pickle

from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils.timezone import now

try:
    from celery import Task
    from celery import shared_task
    from celery.exceptions import CeleryError
    from kombu.utils.uuid import uuid
except ImportError:
    raise ImproperlyConfigured('Missing celery library, please install it')

from .models import CeleryTaskRunLog, CeleryTaskLog, CeleryTaskLogState, CeleryTaskRunLogState
from .utils import LogStringIO


LOGGER = logging.getLogger(__name__)


class LoggedTask(Task):

    abstract = True
    logger_level = logging.WARNING
    retry_error_message = (
        'Task "{task_name}" ({task}) failed on exception: "{exception}", attempt: "{attempt}" and will be retried'
    )
    fail_error_message = 'Task "{task_name}" ({task}) failed on exception: "{exception}", attempt: "{attempt}"'
    stale_time_limit = None
    # Support set retry delay in list. Retry countdown value is get from list where index is attempt
    # number (request.retries)
    default_retry_delays = None

    @property
    def task_run_log(self):
        return CeleryTaskRunLog.objects.get(
            celery_task_id=str(self.request.id),
            retries=self.request.retries
        )

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

        self._create_task_run_log(args, kwargs)

        # Every set attr is sent here
        self.request.output_stream = LogStringIO()
        self.on_start_task(self.task_run_log, args, kwargs)
        return self.run(*args, **kwargs)

    def on_apply_task(self, task_log, args, kwargs, options):
        """
        On apply task is invoked before task was prepared. Therefore task request context is not prepared.
        :param task_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param options: input task options
        """

    def on_retry_task(self, task_run_log, args, kwargs, exc, eta):
        """
        On retry task is invoked before task was retried.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param exc: raised exception which caused retry
        """

        LOGGER.log(self.logger_level, self.retry_error_message.format(
            attempt=self.request.retries, exception=str(exc), task=task_run_log,
            task_name=task_run_log.name, **(kwargs or {})
        ))
        task_run_log.change_and_save(
            state=CeleryTaskLogState.RETRIED,
            error_message=str(exc),
            stop=now(),
            output=self.request.output_stream.getvalue(),
            estimated_time_of_next_retry=eta
        )

    def on_start_task(self, task_run_log, args, kwargs):
        """
        On start task is invoked during task started.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        """

    def on_success_task(self, task_run_log, args, kwargs, retval):
        """
        On start task is invoked if task is successful.
        :param task_run_log: logged celery task instance
        :param args: task args
        :param kwargs: task kwargs
        :param retval: return value of a task
        """
        if retval:
            self.request.output_stream.write('Return value is "{}"'.format(retval))

        task_run_log.change_and_save(
            state=CeleryTaskRunLogState.SUCCEEDED,
            stop=now(),
            result=retval,
            output=self.request.output_stream.getvalue()
        )

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

        LOGGER.log(self.logger_level, self.fail_error_message.format(
            attempt=self.request.retries, exception=str(exc), task=task_run_log, task_name=task_run_log.name, **kwargs
        ))
        task_run_log.change_and_save(
            state=CeleryTaskRunLogState.FAILED,
            stop=now(),
            error_message=str(exc),
            output=self.request.output_stream.getvalue()
        )

    def expire_task(self, task_initiation_log):
        task_initiation_log.change_and_save(is_set_as_stale=True)

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
        if expires is not None:
            return expires
        elif self.expires is not None:
            return self.expires
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
        elif hasattr(settings, 'CELERYD_TASK_STALE_TIME_LIMIT'):
            return settings.CELERYD_TASK_STALE_TIME_LIMIT
        else:
            return None

    def _create_task_log(self, celery_task_id, task_args, task_kwargs, apply_time, eta, expires,
                                stale_time_limit, queue):
        task_input = []
        if task_args:
            task_input += [str(v) for v in task_args]
        if task_kwargs:
            task_input += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]

        return CeleryTaskLog.objects.create(
            celery_task_id=celery_task_id,
            name=self.name,
            queue_name=queue,
            input=', '.join(task_input),
            task_args=task_args,
            task_kwargs=task_kwargs,
            estimated_time_of_first_arrival=eta,
            expires=expires,
            stale=apply_time + timedelta(seconds=stale_time_limit) if stale_time_limit is not None else None
        )

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

    def _first_apply(self, apply_function, args=None, kwargs=None, task_id=None, eta=None, countdown=None, expires=None,
                     time_limit=None, stale_time_limit=None, **options):
        celery_task_id = task_id or uuid()
        apply_time = now()
        time_limit = self._get_time_limit(time_limit)
        eta = self._compute_eta(eta, countdown, apply_time)
        countdown = None
        queue = str(options.get('queue', getattr(self, 'queue', settings.CELERY_DEFAULT_QUEUE)))

        stale_time_limit = self._get_stale_time_limit(stale_time_limit)
        expires = self._compute_expires(expires, time_limit, stale_time_limit, apply_time)

        options.update(dict(
            time_limit=time_limit,
            eta=eta,
            countdown=countdown,
            queue=queue,
            expires=expires,
        ))

        task_initiation = self._create_task_log(
            celery_task_id, args, kwargs, apply_time, eta, expires, stale_time_limit, queue
        )
        self.on_apply_task(task_initiation, args, kwargs, options)
        return apply_function(args=args, kwargs=kwargs, task_id=celery_task_id, **options)

    def apply_async_on_commit(self, args=None, kwargs=None, **options):
        app = self._get_app()
        if app.conf.task_always_eager:
            self.apply_async(args=args, kwargs=kwargs, **options)
        else:
            self_inst = self
            transaction.on_commit(
                lambda: self_inst.apply_async(args=args, kwargs=kwargs, **options)
            )

    def apply(self, args=None, kwargs=None, **options):
        if self.request.id:
            return super().apply(args=args, kwargs=kwargs, **options)
        else:
            return self._first_apply(super().apply, args, kwargs, **options)

    def apply_async(self, args=None, kwargs=None, **options):
        app = self._get_app()
        if self.request.id or app.conf.task_always_eager:
            return super().apply_async(args=args, kwargs=kwargs, **options)
        else:
            return self._first_apply(super().apply_async, args, kwargs, **options)

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


def obj_to_string(obj):
    return base64.encodebytes(pickle.dumps(obj)).decode('utf8')


def string_to_obj(obj_string):
    return pickle.loads(base64.decodebytes(obj_string.encode('utf8')))


@shared_task(
    base=LoggedTask,
    bind=True,
    name='call_django_command'
)
def call_django_command(self, command_name, command_args=None):
    command_args = [] if command_args is None else command_args
    call_command(
        command_name,
        settings=os.environ.get('DJANGO_SETTINGS_MODULE'),
        *command_args,
        stdout=self.request.output_stream,
        stderr=self.request.output_stream,
    )
