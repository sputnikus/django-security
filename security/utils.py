import re
from importlib import import_module
from io import StringIO
from time import time
import datetime
import decimal
import uuid

import isodate

from django.core.exceptions import ImproperlyConfigured
from django.db import router
from django.utils.timezone import now, is_aware
from django.utils.duration import duration_iso_string

from .config import settings
from .enums import LoggerName


def get_throttling_validators(name):
    try:
        return getattr(import_module(settings.DEFAULT_THROTTLING_VALIDATORS_PATH), name)
    except (ImportError, AttributeError):
        raise ImproperlyConfigured('Throttling validator configuration {} is not defined'.format(name))


def remove_nul_from_string(value):
    return value.replace('\x00', '')


def is_atty_string(s):
    return bool(re.search(r'^' + re.escape('\x1b[') + r'\d+m$', s))


def truncate_lines_from_left(value, max_length):
    """
    Firstly text is truncated according to max_length.
    Next step is find next character '\n' and while text before \n is removed. On the start is added '…'

    If there is only one line (without \n) which is longer than max_length. Whole line is removed and replaced with …\n
    """
    if len(value) <= max_length:
        return value

    # value 2 is added because of …\n
    truncated_value = value[len(value) + 2 - max_length:]
    truncated_value_split_by_newline = truncated_value.split('\n', 1)
    return f'…\n{"" if len(truncated_value_split_by_newline) == 1 else truncated_value_split_by_newline[1]}'


class LogStringIO(StringIO):

    BOLD = '\x1b[1m'
    RESET = '\x1b[0m'

    def __init__(self, flush_callback=None, flush_timeout=None, write_time=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_closed = False
        self._last_newline = 0
        self._flush_callback = flush_callback
        self._write_time = write_time
        self._write_time_to_line = self._write_time
        self._last_flush_time = time()
        self._flush_timeout = settings.LOG_STRING_IO_FLUSH_TIMEOUT if flush_timeout is None else flush_timeout
        self._flushed = True
        self._next_line_number = 1

    def _flush(self, force=False):
        if (not self._flushed and self._flush_callback
                and (force or time() - self._last_flush_time > self._flush_timeout)):
            self._flush_callback(self)
            self._last_flush_time = time()
            self._flushed = True

    def _write_line_number_and_time(self):
        if self._write_time:
            super().write('{}{}[{}] [{}]{} '.format(
                self.RESET,
                self.BOLD,
                self._next_line_number,
                now().strftime('%d-%m-%Y %H:%M:%S'),
                self.RESET
            ))
            self._write_time_to_line = False

    def write(self, s):
        if not self._is_closed:
            self._flushed = False
            lines = s.split('\n')

            for i, line in enumerate(lines):
                cursor_first = True
                for cursor_block in line.split('\r'):
                    if not cursor_first:
                        self.seek(self._last_newline)
                        self.truncate()
                        self._write_time_to_line = self._write_time
                    cursor_first = False
                    if self._write_time_to_line and not is_atty_string(cursor_block):
                        self._write_line_number_and_time()
                    super().write(cursor_block)

                if i != len(lines) - 1:
                    super().write('\n')
                    self._next_line_number += 1
                    self._last_newline = self.tell()
                    self._write_time_to_line = self._write_time

            self._truncate_by_max_length()
            self._flush()

    def _truncate_by_max_length(self):
        """
        StringIO value is truncated from left side to maximal length defined in LOG_STRING_OUTPUT_TRUNCATE_LENGTH.
        Because too frequent string truncation can cause high CPU load, log string is truncated by more characters.
        The value is defined in LOG_STRING_OUTPUT_TRUNCATE_OFFSET. Eg
            LOG_STRING_OUTPUT_TRUNCATE_LENGTH = 10000
            LOG_STRING_OUTPUT_TRUNCATE_OFFSET = 1000

            if text is longer than 10000 character is truncated to 9000 characters.

        To better readability the text is further truncated to the following newline.
        """
        if self.tell() > settings.LOG_STRING_OUTPUT_TRUNCATE_LENGTH:
            original_value = self.getvalue()
            truncated_value = truncate_lines_from_left(
                self.getvalue(),
                settings.LOG_STRING_OUTPUT_TRUNCATE_LENGTH - settings.LOG_STRING_OUTPUT_TRUNCATE_OFFSET
            )
            self._last_newline = self._last_newline - (len(original_value) - len(truncated_value))
            self.seek(0)
            self.truncate()
            super().write(truncated_value)
            if truncated_value.endswith('\n'):
                self._write_line_number_and_time()

    def isatty(self):
        return True

    def close(self):
        self._is_closed = True
        self._flush(force=True)
        super().close()


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


def update_logged_request_data(request, related_objects=None, slug=None, extra_data=None):
    input_request_logger = getattr(request, 'input_request_logger', None)
    if input_request_logger:
        if related_objects:
            input_request_logger.add_related_objects(*related_objects)
        if slug:
            input_request_logger.set_slug(slug)
        if extra_data:
            input_request_logger.update_extra_data(extra_data)


def get_object_triple(obj):
    from django.contrib.contenttypes.models import ContentType

    if isinstance(obj, (list, tuple)) and len(obj) == 3:
        return tuple(obj)
    else:
        content_type = ContentType.objects.get_for_model(obj)
        return router.db_for_write(content_type.model_class()), content_type.pk, obj.pk


def serialize_data(o):
    if isinstance(o, datetime.datetime):
        r = o.isoformat()
        if o.microsecond:
            r = r[:23] + r[26:]
        if r.endswith('+00:00'):
            r = r[:-6] + 'Z'
        return {'@type': 'datetime',  '@value': r}
    elif isinstance(o, datetime.date):
        return {'@type': 'date',  '@value': o.isoformat()}
    elif isinstance(o, datetime.time):
        if is_aware(o):
            raise ValueError("JSON can't represent timezone-aware times.")
        r = o.isoformat()
        if o.microsecond:
            r = r[:12]
        return {'@type': 'time', '@value': r}
    elif isinstance(o, datetime.timedelta):
        return {'@type': 'timedelta', '@value': duration_iso_string(o)}
    elif isinstance(o, decimal.Decimal):
        return {'@type': 'decimal', '@value': str(o)}
    elif isinstance(o, uuid.UUID):
        return {'@type': 'uuid', '@value': str(o)}
    elif isinstance(o, (list, tuple, set)):
        return [serialize_data(v) for v in o]
    elif isinstance(o, dict):
        return {
            k: serialize_data(v) for k, v in o.items()
        }
    else:
        return o


def deserialize_data(o):
    if isinstance(o, dict) and set(o.keys()) == {'@type', '@value'}:
        o_type, o_value = o['@type'], o['@value']
        if o_type == 'uuid':
            return uuid.UUID(o_value)
        elif o_type == 'decimal':
            return decimal.Decimal(o_value)
        elif o_type == 'timedelta':
            return isodate.parse_duration(o_value)
        elif o_type == 'time':
            return isodate.parse_time(o_value)
        elif o_type == 'date':
            return isodate.parse_date(o_value)
        elif o_type == 'datetime':
            return isodate.parse_datetime(o_value)
    elif isinstance(o, dict):
        return {
            k: deserialize_data(v) for k, v in o.items()
        }
    elif isinstance(o, list):
        return [deserialize_data(v) for v in o]
    else:
        return o


def get_run_logger():
    """
    Return celery task run or command logger
    """
    from security.logging.common import get_last_logger

    return get_last_logger(LoggerName.CELERY_TASK_RUN) or get_last_logger(LoggerName.COMMAND)


def add_related_objects_to_run_logger(obj):
    """
    Add related object to celery task run or command logger
    """
    run_logger = get_run_logger()
    if run_logger:
        run_logger.add_related_objects(obj)
