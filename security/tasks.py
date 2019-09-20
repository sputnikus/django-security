import os
import base64
import logging
import pickle
import sys
from io import StringIO

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

from chamber.utils.transaction import atomic_with_signals

from .models import CeleryTaskLog, CeleryTaskLogState


LOGGER = logging.getLogger(__name__)


class LoggedTask(Task):

    abstract = True
    logger_level = logging.WARNING

    def push_request(self, *args, **kwargs):
        task_id = self.request.id
        output_stream = self.request.output_stream
        super().push_request(*args, **kwargs)
        self.request.id = task_id
        self.request.output_stream = output_stream

    def get_task(self):
        return CeleryTaskLog.objects.get(pk=self.request.id)

    def __call__(self, *args, **kwargs):
        # Every set attr is send here
        self.request.output_stream = StringIO()
        self.on_start(self.request.id, args, kwargs)
        super().__call__(*args, **kwargs)

    def _call_callback(self, event, *args, **kwargs):
        if hasattr(self, 'on_{}_callback'.format(event)):
            getattr(self, 'on_{}_callback'.format(event))(*args, **kwargs)

    def on_apply(self, task_id, args, kwargs):
        self._call_callback('apply', task_id, args, kwargs)

    def on_start(self, task_id, args, kwargs):
        self.get_task().change_and_save(state=CeleryTaskLogState.ACTIVE, start=now())
        self._call_callback('start', task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        if retval:
            self.request.output_stream.write('Return value is "{}"'.format(retval))

        self.get_task().change_and_save(
            state=CeleryTaskLogState.SUCCEEDED,
            stop=now(),
            output=self.request.output_stream.getvalue()
        )
        self._call_callback('success', task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            self.get_task().change_and_save(
                state=CeleryTaskLogState.FAILED,
                stop=now(),
                error_message=einfo,
                output=self.request.output_stream.getvalue()
            )
        except CeleryTaskLog.DoesNotExist:
            pass
        self._call_callback('failure', task_id, args, kwargs)

    def _create_task(self, options, task_args, task_kwargs):
        task_input = []
        if task_args:
            task_input += [str(v) for v in task_args]
        if task_kwargs:
            task_input += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]

        task = CeleryTaskLog.objects.create(
            name=self.name,
            state=CeleryTaskLogState.WAITING,
            queue_name=options.get('queue', getattr(self, 'queue', settings.CELERY_DEFAULT_QUEUE)),
            input=', '.join(task_input),
        )
        return str(task.pk)

    def apply_async_on_commit(self, args=None, kwargs=None, **options):
        task_id = self._create_task(options, args, kwargs)
        self.on_apply(task_id, args, kwargs)
        if sys.argv[1:2] == ['test']:
            super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)
        else:
            super_inst = super()
            transaction.on_commit(
                lambda: super_inst.apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)
            )

    def apply_async(self, args=None, kwargs=None, **options):
        task_id = self._create_task(options, args, kwargs)
        self.on_apply(task_id, args, kwargs)
        return super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)

    def log_and_retry(self, attempt, exception_message=None, queue=None, *args, **kwargs):
        LOGGER.log(self.logger_level, self.retry_error_message.format(
            attempt=attempt, exception_message=exception_message, **kwargs
        ))
        if attempt <= len(self.repeat_timeouts):
            self.apply_async_on_commit(
                args=args,
                kwargs={**kwargs, 'attempt': attempt+1},
                countdown=self.repeat_timeouts[attempt - 1] * 60,
                queue=queue or getattr(self, 'queue', settings.CELERY_DEFAULT_QUEUE)
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
@atomic_with_signals
def call_django_command(self, command_name, command_args=None):
    command_args = [] if command_args is None else command_args
    call_command(
        command_name,
        settings=os.environ.get('DJANGO_SETTINGS_MODULE'),
        *command_args,
        stdout=self.request.output_stream,
        stderr=self.request.output_stream,
    )
