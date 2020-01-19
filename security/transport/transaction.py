import itertools

from threading import local

from django.utils.decorators import ContextDecorator

from security.models import OutputLoggedRequest


_related_objects_list = local()
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
        for obj in self.related_objects or ():
            if obj.__class__.objects.filter(pk=obj.pk).exists():
                output_logged_request.related_objects.create(content_object=obj)


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


def log_output_request(data, related_objects=None):
    """
    Helper for logging output requests
    :param data: dict of input attributes of OutputLoggedRequest model
    :param related_objects: objects that will be related to OutputLoggedRequest object
    """
    if is_active_logged_requests():
        output_logged_requests = _output_logged_requests_list.value[-1]
        output_logged_requests.append(OutputLoggedRequestContext(data, related_objects))
    else:
        output_logged_request = OutputLoggedRequest.objects.create(**data)
        if related_objects:
            [output_logged_request.related_objects.create(content_object=obj) for obj in related_objects]


def is_active_logged_requests():
    """
    :param using: database alias
    :return: True if block of code is surrounded with atomic_log operator
    """
    return hasattr( _output_logged_requests_list, 'value') and  _output_logged_requests_list.value



def get_all_request_related_objects():
    """
    Return all related selected with log_request_related_objects decorator.
    :return: list of request related objects
    """
    related_objects_list = getattr(_related_objects_list, 'value', [])
    return list(itertools.chain(*related_objects_list))


class LogRequestRelatedObjects(ContextDecorator):
    """
    Context decorator that adds related objects to all requests inside code block
    """

    def __init__(self, related_objects):
        self.related_objects = related_objects

    def __enter__(self):
        related_objects_list = getattr(_related_objects_list, 'value', [])
        related_objects_list.append(self.related_objects)
        _related_objects_list.value = related_objects_list

    def __exit__(self, exc_type, exc_value, traceback):
        _related_objects_list.value.pop()


def log_request_related_objects(related_objects):
    """
    Decorator that adds related objects to all requests inside code block.
    """
    return LogRequestRelatedObjects(related_objects)
