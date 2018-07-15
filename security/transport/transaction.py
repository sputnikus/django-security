from django.db import DEFAULT_DB_ALIAS
from django.db.transaction import get_connection
from django.utils.decorators import ContextDecorator

from security.models import OutputLoggedRequest


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

    def __init__(self, using):
        self.using = using

    def __enter__(self):
        connection = get_connection(self.using)
        output_logged_requests = getattr(connection, 'output_logged_requests', [])
        output_logged_requests.append([])
        connection.output_logged_requests = output_logged_requests

    def __exit__(self, exc_type, exc_value, traceback):
        connection = get_connection(self.using)
        output_logged_requests = connection.output_logged_requests.pop()
        if connection.output_logged_requests:
            connection.output_logged_requests[-1] += output_logged_requests
        else:
            [output_logged_request.create() for output_logged_request in output_logged_requests]


def atomic_log(using=None):
    """
    Decorator that surrounds atomic block, ensures that logged output requests will be stored inside database in case
    of DB rollback
    """
    if callable(using):
        return AtomicLog(DEFAULT_DB_ALIAS)(using)
    else:
        return AtomicLog(using)


def log_output_request(data, related_objects=None, using=None):
    """
    Helper for logging output requests
    :param data: dict of input attributes of OutputLoggedRequest model
    :param related_objects: objects that will be related to OutputLoggedRequest object
    :param using: database alias
    """
    if is_active_logged_requests(using):
        output_logged_requests = get_connection(using).output_logged_requests[-1]
        output_logged_requests.append(OutputLoggedRequestContext(data, related_objects))
    else:
        output_logged_request = OutputLoggedRequest.objects.create(**data)
        if related_objects:
            [output_logged_request.related_objects.create(content_object=obj) for obj in related_objects]


def is_active_logged_requests(using=None):
    """
    :param using: database alias
    :return: True if block of code is surrounded with atomic_log operator
    """
    return hasattr(get_connection(using), 'output_logged_requests') and get_connection(using).output_logged_requests
