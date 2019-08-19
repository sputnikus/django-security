import os
import base64
import logging
import pickle
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils.timezone import now

try:
    from celery import Task
    from celery import shared_task
except ImportError:
    raise ImproperlyConfigured('Missing celery library, please install it')

from chamber.shortcuts import change_and_save
from chamber.utils.transaction import atomic_with_signals

from .models import CeleryTaskLog, CeleryTaskLogState


LOGGER = logging.getLogger(__name__)


class LoggedTask(Task):

    abstract = True
    logger_level = logging.WARNING

    def get_task(self, task_id):
        return CeleryTaskLog.objects.get(pk=task_id)

    def __call__(self, *args, **kwargs):
        # Every set attr is send here
        self.on_start(self.request.id, args, kwargs)
        super().__call__(*args, **kwargs)

    def _call_callback(self, event, *args, **kwargs):
        if hasattr(self, 'on_{}_callback'.format(event)):
            getattr(self, 'on_{}_callback'.format(event))(*args, **kwargs)

    def on_apply(self, task_id, args, kwargs):
        self._call_callback('apply', task_id, args, kwargs)

    def on_start(self, task_id, args, kwargs):
        self.get_task(task_id).change_and_save(state=CeleryTaskLogState.ACTIVE, start=now())
        self._call_callback('start', task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        self.get_task(task_id).change_and_save(state=CeleryTaskLogState.SUCCEEDED, stop=now())
        self._call_callback('success', task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            self.get_task(task_id).change_and_save(state=CeleryTaskLogState.FAILED, stop=now(), error_message=einfo)
        except CeleryTask.DoesNotExist:
            pass
        self._call_callback('failure', task_id, args, kwargs)

    def _create_task(self, options):
        task = CeleryTaskLog.objects.create(
            name=self.name, state=CeleryTaskLogState.WAITING,
            queue_name=options.get('queue', settings.CELERY_DEFAULT_QUEUE)
        )
        return str(task.pk)

    def _get_args(self, task_id, args):
        return (task_id,) + tuple(args or ())

    def apply_async_on_commit(self, args=None, kwargs=None, **options):
        task_id = self._create_task(options)
        args = self._get_args(task_id, args)
        self.on_apply(task_id, args, kwargs)
        if sys.argv[1:2] == ['test']:
            super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)
        else:
            super_inst = super()
            transaction.on_commit(
                lambda: super_inst.apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)
            )

    def apply_async(self, args=None, kwargs=None, **options):
        task_id = self._create_task(options)
        args = self._get_args(task_id, args)
        self.on_apply(task_id, args, kwargs)
        return super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)

    def log_and_retry(self, attempt, exception_message=None, *args, **kwargs):
        LOGGER.log(self.logger_level, self.retry_error_message.format(
            attempt=attempt, exception_message=exception_message, **kwargs
        ))
        if attempt <= len(self.repeat_timeouts):
            self.apply_async_on_commit(
                args=args,
                kwargs={**kwargs, 'attempt': attempt+1},
                countdown=self.repeat_timeouts[attempt - 1] * 60,
                queue=self.queue
            )


def obj_to_string(obj):
    return base64.encodebytes(pickle.dumps(obj)).decode('utf8')


def string_to_obj(obj_string):
    return pickle.loads(base64.decodebytes(obj_string.encode('utf8')))


@shared_task(
    base=LoggedTask,
    bind=True,
    name='call_django_command',
)
@atomic_with_signals
def call_django_command(self, task_id, command_name, command_args=None):
    command_args = [] if command_args is None else command_args
    call_command(command_name, '--settings={}'.format(os.environ.get('DJANGO_SETTINGS_MODULE')), *command_args)

