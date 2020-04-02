import itertools
from contextlib import ContextDecorator
from threading import local

from security.models import OutputLoggedRequest


_input_logged_request = local()
_output_logged_requests_list = local()


class OutputLoggedRequestContext:
    """
    Data structure that stores data for creation OutputLoggedRequest model object
    """

    def __init__(self, data, related_objects=None):
        self.data = data
        self.related_objects = related_objects

    def create(self, input_logged_request=None):
        output_logged_request = OutputLoggedRequest.objects.create(
            input_logged_request=input_logged_request, **self.data
        )
        output_logged_request.related_objects.add(*self.related_objects)
        return output_logged_request


class AtomicLog(ContextDecorator):
    """
    Context decorator that stores logged requests to database connections and inside exit method
    stores it to the database
    """

    def __enter__(self):
        output_logged_requests_list = getattr(_output_logged_requests_list, 'value', [])
        output_logged_requests_list.append([])
        _output_logged_requests_list.value = output_logged_requests_list

    def __exit__(self, exc_type, exc_value, traceback):
        output_logged_requests = _output_logged_requests_list.value.pop()
        if _output_logged_requests_list.value:
            _output_logged_requests_list.value[-1] += output_logged_requests
        else:
            [output_logged_request.create() for output_logged_request in output_logged_requests]


def atomic_log(function=None):
    """
    Decorator that surrounds atomic block, ensures that logged output requests will be stored inside database in case
    of DB rollback
    """
    if callable(function):
        return AtomicLog()(function)
    else:
        return AtomicLog()


def is_active_logged_requests():
    """
    :param using: database alias
    :return: True if block of code is surrounded with atomic_log operator
    """
    return hasattr(_output_logged_requests_list, 'value') and _output_logged_requests_list.value


def get_all_request_related_objects():
    """
    Return all related selected with log_request_related_objects decorator.
    :return: list of request related objects
    """
    related_objects_list = getattr(_input_logged_request, 'related_objects_list', [])
    return list(itertools.chain(*related_objects_list))


def get_request_slug():
    """
    Return last slug defined with log_request_related_objects decorator.
    :return input logged request slug
    """
    slug_list = getattr(_input_logged_request, 'slug_list', [])
    return None if not slug_list else slug_list[-1]


class LogRequestRelatedObjects(ContextDecorator):
    """
    Context decorator that adds related objects to all requests inside code block
    """

    def __init__(self, slug, related_objects):
        self.slug = slug
        self.related_objects = [] if related_objects is None else related_objects

    def __enter__(self):
        related_objects_list = getattr(_input_logged_request, 'related_objects_list', [])
        slug_list = getattr(_input_logged_request, 'slug_list', [])

        last_related_objects_slug = None if not slug_list else slug_list[-1]

        slug_list.append(last_related_objects_slug if self.slug is None else self.slug)
        related_objects_list.append(self.related_objects)
        _input_logged_request.related_objects_list = related_objects_list
        _input_logged_request.slug_list = slug_list

    def __exit__(self, exc_type, exc_value, traceback):
        _input_logged_request.related_objects_list.pop()
        _input_logged_request.slug_list.pop()


def log_request_related_objects(slug=None, related_objects=None):
    """
    Decorator that adds related objects to all requests inside code block.
    """
    return LogRequestRelatedObjects(slug, related_objects)
