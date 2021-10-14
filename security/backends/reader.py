from django.core.exceptions import ImproperlyConfigured
from importlib import import_module

from security.config import settings

from .app import SecurityBackend


def get_reader_backend_app():
    if not SecurityBackend.registered_readers:
        raise ImproperlyConfigured('No registered backend reader was set')
    if settings.BACKEND_READER is not None:
        if settings.BACKEND_READER not in SecurityBackend.registered_readers:
            raise ImproperlyConfigured(f'Backend reader "{settings.BACKEND_READER}" is not registered')
        return SecurityBackend.registered_readers[settings.BACKEND_READER]
    else:
        return next(iter(SecurityBackend.registered_readers.values()))


def get_reader_backend_helpers_module():
    return import_module(f'{get_reader_backend_app().name}.reader')


def get_count_input_requests(from_time, ip=None, path=None, view_slug=None, slug=None, method=None,
                             exclude_log_id=None):
    return get_reader_backend_helpers_module().get_count_input_requests(
        from_time, ip, path, view_slug, slug, method, exclude_log_id
    )


def get_logs_related_with_object(logger_name, related_object):
    return get_reader_backend_helpers_module().get_logs_related_with_object(
        logger_name, related_object
    )
