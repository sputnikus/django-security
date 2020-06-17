import atexit
import logging
import re
import sys
import traceback
from contextlib import ContextDecorator
from importlib import import_module
from io import StringIO
from threading import local

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import request_finished
from django.db.transaction import get_connection
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils.timezone import now

from .config import settings


output_logged_request_logger = logging.getLogger('security.output_request')


class LogManagementError(Exception):
    pass


class OutputLoggedRequestContext:
    """
    Data structure that stores data for creation OutputLoggedRequest model object
    """

    def __init__(self, data, related_objects=None):
        self.data = data
        self.related_objects = related_objects

    def create(self, logs=None):
        from security.models import OutputLoggedRequest

        logs = [] if logs is None else logs
        output_logged_request = OutputLoggedRequest.objects.create(
            **self.data
        )
        related_objects = list(self.related_objects) + logs
        output_logged_request.related_objects.add(*related_objects)
        return output_logged_request


class LogContextStackFrame:

    def __init__(self, input_logged_request, command_log, celery_task_log, celery_task_run_log,
                 output_requests_related_objects,
                 output_requests_slug):
        self.input_logged_request = input_logged_request
        self.command_log = command_log
        self.celery_task_log = celery_task_log
        self.celery_task_run_log = celery_task_run_log
        self.output_requests_related_objects = (
            list(output_requests_related_objects) if output_requests_related_objects else []
        )
        self.output_requests_slug = output_requests_slug
        self.output_logged_requests = []

    def fork(self, input_logged_request, command_log, celery_task_log, celery_task_run_log,
             output_requests_related_objects, output_requests_slug):
        output_requests_related_objects = (
            list(output_requests_related_objects) if output_requests_related_objects else []
        )
        return LogContextStackFrame(
            input_logged_request or self.input_logged_request,
            command_log or self.command_log,
            celery_task_log or self.celery_task_log,
            celery_task_run_log or self.celery_task_run_log,
            output_requests_related_objects=(
                self.output_requests_related_objects + output_requests_related_objects
            ),
            output_requests_slug=self.output_requests_slug if output_requests_slug is None else output_requests_slug
        )

    def join(self, other_context):
        self.output_logged_requests += other_context.output_logged_requests

    def get_logs(self):
        return list(
            filter(None, [
                self.input_logged_request,
                self.command_log,
                self.celery_task_log,
                self.celery_task_run_log,
            ])
        )

    def save(self):
        for output_logged_request in self.output_logged_requests:
            output_logged_request.create(self.get_logs())


class LogContextManager(local):

    def __init__(self):
        self.clear()
        request_finished.connect(self._request_finished_receiver)
        if 'reversion' in django_settings.INSTALLED_APPS:
            from reversion.signals import post_revision_commit

            post_revision_commit.connect(self._post_revision_commit)

    def is_active(self):
        """Returns whether there is an active revision for this thread."""
        return bool(self._stack)

    def _assert_active(self):
        """Checks for an active revision, throwning an exception if none."""
        if not self.is_active():  # pragma: no cover
            raise LogManagementError('There is no active context log for this thread')

    @property
    def input_logged_request(self):
        return self._current_frame.input_logged_request

    @property
    def command_log(self):
        return self._current_frame.command_log

    @property
    def celery_task_log(self):
        return self._current_frame.celery_task_log

    @property
    def celery_task_run_log(self):
        return self._current_frame.celery_task_run_log

    def get_logs(self):
        return self._current_frame.get_logs()

    @property
    def _current_frame(self):
        self._assert_active()
        return self._stack[-1]

    def start(self, input_logged_request=None, command_log=None, celery_task_log=None, celery_task_run_log=None,
              output_requests_related_objects=None, output_requests_slug=None):
        """
        Begins a context log for this thread.

        This MUST be balanced by a call to `end`
        """
        if self.is_active():
            self._stack.append(
                self._current_frame.fork(
                    input_logged_request,
                    command_log,
                    celery_task_log,
                    celery_task_run_log,
                    output_requests_related_objects,
                    output_requests_slug
                )
            )
        else:
            self._stack.append(
                LogContextStackFrame(
                    input_logged_request,
                    command_log,
                    celery_task_log,
                    celery_task_run_log,
                    output_requests_related_objects or [],
                    output_requests_slug
                )
            )

    def end(self):
        self._assert_active()
        connection = get_connection(settings.LOG_DB_NAME)
        stack_frame = self._stack.pop()
        if self._stack and connection.in_atomic_block:
            self._current_frame.join(stack_frame)
        elif self._stack:
            stack_frame.save()
        else:
            try:
                stack_frame.save()
            finally:
                self.clear()

    def clear(self):
        self._stack = []

    def _request_finished_receiver(self, **kwargs):
        """
        Called at the end of a request, ensuring that any open logs
        are closed. Not closing all active revisions can cause memory leaks
        and weird behaviour.
        """
        while self.is_active():  # pragma: no cover
            self.end()

    def log_output_requests(self, output_logged_request_context):
        connection = get_connection(settings.LOG_DB_NAME)

        if connection.in_atomic_block:
            self._current_frame.output_logged_requests.append(output_logged_request_context)
        else:
            output_logged_request_context.create(logs=self.get_logs())

    def get_output_request_related_objects(self):
        if not self.is_active():
            return []

        return self._current_frame.output_requests_related_objects

    def get_output_request_slug(self):
        if not self.is_active():
            return None

        return self._current_frame.output_requests_slug

    def _post_revision_commit(self, **kwargs):
        """
        Called as a post save of revision model of the reversion library.
        If log context manager is active input logged request, command
        log or celery task run log is joined with revision via related objects.
        """
        revision = kwargs['revision']
        if self.is_active():
            if self.input_logged_request:
                self.input_logged_request.related_objects.add(revision)
            if self.command_log:
                self.command_log.related_objects.add(revision)
            if self.celery_task_run_log:
                self.celery_task_run_log.related_objects.add(revision)


log_context_manager = LogContextManager()


class AtomicLog(ContextDecorator):
    """
    Context decorator that stores logged requests to database connections and inside exit method
    stores it to the database
    """

    def __init__(self, input_logged_request=None, command_log=None, celery_task_log=None, celery_task_run_log=None,
                 output_requests_related_objects=None, output_requests_slug=None):
        self._command_log = command_log
        self._celery_task_log = celery_task_log
        self._celery_task_run_log = celery_task_run_log
        self._input_logged_request = input_logged_request
        self._output_requests_related_objects = (
            [] if output_requests_related_objects is None else list(output_requests_related_objects)
        )
        self._output_requests_slug = output_requests_slug

    def __enter__(self):
        log_context_manager.start(
            self._input_logged_request,
            self._command_log,
            self._celery_task_log,
            self._celery_task_run_log,
            self._output_requests_related_objects,
            self._output_requests_slug,
        )

    def __exit__(self, exc_type, exc_value, traceback):
        log_context_manager.end()


def log_output_request(data, related_objects=None):
    """
    Helper for logging output requests
    :param data: dict of input attributes of OutputLoggedRequest model
    :param related_objects: objects that will be related to OutputLoggedRequest object
    """
    output_logged_request_context = OutputLoggedRequestContext(data, related_objects)
    if log_context_manager.is_active():
        log_context_manager.log_output_requests(output_logged_request_context)
    else:
        output_logged_request_context.create()

    if settings.LOG_OUTPUT_REQUESTS:
        output_logged_request_logger.info(
            ('"%s" "%s" "%s" "%s" "%s" "%s" "%s" "%s"'),
            data.get('request_timestamp', ''),
            data.get('response_timestamp', ''),
            data.get('response_time', ''),
            data.get('response_code', ''),
            data.get('host', ''),
            data.get('path', ''),
            data.get('method', ''),
            data.get('slug', ''),
        )


def is_base_collection(v):
    return isinstance(v, (list, tuple, set))


def get_throttling_validators(name):
    try:
        return getattr(import_module(settings.DEFAULT_THROTTLING_VALIDATORS_PATH), name)
    except (ImportError, AttributeError):
        raise ImproperlyConfigured('Throttling validator configuration {} is not defined'.format(name))


def get_headers(request):
    regex = re.compile('^HTTP_')
    return dict((regex.sub('', header), value) for (header, value)
                in request.META.items() if header.startswith('HTTP_'))


def remove_nul_from_string(value):
    return value.replace('\x00', '')


class LogStringIO(StringIO):

    def __init__(self, post_write_callback=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_newline = 0
        self._post_write_callback = post_write_callback

    def _post_write(self):
        if self._post_write_callback:
            self._post_write_callback(self)

    def write(self, s):
        line_first = True
        for line in s.split('\n'):
            if not line_first:
                super().write('\n')
                self._last_newline = self.tell()
            cursor_first = True
            for cursor_block in line.split('\r'):
                if not cursor_first:
                    self.seek(self._last_newline)
                    self.truncate()
                cursor_first = False
                super().write(cursor_block)
            line_first = False
        self._post_write()

    def isatty(self):
        return True


class TeeStringIO:
    """
    StringIO that additionally writes to another stream(s).
    """
    ANSI_ESCAPE_REGEX = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

    def __init__(self, out, log_stream):
        self._out = out
        self._log_stream = log_stream
        self._last_newline = 0
        super().__init__()

    def write(self, s):
        if self.isatty():
            self._out.write(s)
        else:
            self._out.write(self.ANSI_ESCAPE_REGEX.sub('', s))
        self._log_stream.write(s)

    def __getattr__(self, name):
        return getattr(self._out, name)

    def isatty(self):
        return hasattr(self._out, 'isatty') and self._out.isatty()

    def flush(self):
        self._out.flush()
        self._log_stream.flush()


class CommandLogger(StringIO):
    """
    A helper class that runs a django command and logs details about its run into DB.
    """

    def __init__(self, command_function, command_args=None, command_kwargs=None, stdout=None, stderr=None, **kwargs):
        """
        Initializes the command logger.

        Arguments:
            command_function: Callable that implements the command.
            stdout: Custom stream where command's standard output will be written.
            stderr: Custom stream where command's error output will be written.
            **kwargs: Keyword arguments passed to CommandLog model.
        """
        assert 'name' in kwargs, 'Key name must be provided in kwargs'

        self.command_function = command_function
        self.command_args = command_args or ()
        self.command_kwargs = command_kwargs or {}

        self.kwargs = kwargs
        self.stdout = stdout if stdout else sys.stdout
        self.stderr = stderr if stderr else sys.stderr

    def _store_log_output(self, output_stream):
        self.command_log.change_and_save(
            output=output_stream.getvalue(),
            update_only_changed_fields=True
        )

    def run(self):
        """
        Runs the command function and returns its return value or re-raises any exceptions. The run of the command will
        not be logged if it is in excluded commands setting.
        """
        from security.models import CommandLog
        from security.decorators import atomic_log

        if self.kwargs['name'] in settings.COMMAND_LOG_EXCLUDED_COMMANDS:
            return self.command_function(
                stdout=self.stdout, stderr=self.stderr, *self.command_args, **self.command_kwargs
            )

        self.command_log = CommandLog.objects.create(start=now(), **self.kwargs)
        if log_context_manager.is_active():
            related_objects = log_context_manager.get_logs()
            for related_object in related_objects:
                self.command_log.related_objects.add(related_object)

        self.output = LogStringIO(post_write_callback=self._store_log_output)
        stdout = TeeStringIO(self.stdout, self.output)
        stderr = TeeStringIO(self.stderr, self.output)

        # register call of the finish method in case the command exits the interpreter prematurely
        atexit.register(lambda: self._finish(error_message='Command was killed'))

        try:
            with atomic_log(command_log=self.command_log):
                ret_val = self.command_function(
                    stdout=stdout, stderr=stderr, *self.command_args, **self.command_kwargs
                )
                self._finish(success=True)
                return ret_val
        except Exception as ex:  # pylint: disable=W0703
            self._finish(success=False, error_message=traceback.format_exc())
            raise ex

    def _finish(self, success=False, error_message=None):
        if self.command_log.stop is None:
            stop = now()
            self.command_log.change_and_save(
                output=self.output.getvalue(),
                stop=stop,
                time=(stop - self.command_log.start).total_seconds(),
                is_successful=success,
                error_message=error_message
            )


def regex_sub_groups_global(pattern, repl, string):
    """
    Globally replace all groups inside pattern with `repl`.
    If `pattern` doesn't have groups the whole match is replaced.
    """
    for search in reversed(list(re.finditer(pattern, string))):
        for i in range(len(search.groups()), 0 if search.groups() else -1, -1):
            start, end = search.span(i)
            string = string[:start] + repl + string[end:]
    return string


def get_view_from_request_or_none(request):
    try:
        return resolve(request.path).func
    except Resolver404:
        return None


is_running_migration = False
