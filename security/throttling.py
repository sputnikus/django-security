from datetime import timedelta

from django.utils import timezone
from django.utils.translation import ugettext as _

from .models import LoggedRequest
from .utils import get_client_ip
from .exception import ThrottlingException


class ThrottlingValidator(object):

    def validate(self, request):
        raise NotImplemented


class PerRequestThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('Slow down')):
        self.timeframe = timeframe
        self.throttle_at = throttle_at
        self.description = description

    def validate(self, request):
        count_same_requests = LoggedRequest.objects.filter(ip=get_client_ip(request), path=request.path,
                                                       timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe))\
                                                       .count()
        if count_same_requests > self.throttle_at:
            raise ThrottlingException(self.description)


def throttling(validator):

    def decorator(function):
        def _throttling(self, request, *args, **kwargs):
            validator.validate(request)
            return function(self, request, *args, **kwargs)
        return _throttling

    return decorator
