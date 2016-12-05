import re

from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_throttling_validators(name):
    try:
        return getattr(import_module(settings.SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH), name)
    except ImportError:
        raise ImproperlyConfigured('Throttling validator configuration {} is not defined'.format(name))


def get_headers(request):
    regex = re.compile('^HTTP_')
    return dict((regex.sub('', header), value) for (header, value)
                in request.META.items() if header.startswith('HTTP_'))
