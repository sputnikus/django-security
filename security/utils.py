import re
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured

from .config import SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH


def get_throttling_validators(name):
    try:
        return getattr(import_module(SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH), name)
    except (ImportError, AttributeError):
        raise ImproperlyConfigured('Throttling validator configuration {} is not defined'.format(name))


def get_headers(request):
    regex = re.compile('^HTTP_')
    return dict((regex.sub('', header), value) for (header, value)
                in request.META.items() if header.startswith('HTTP_'))
