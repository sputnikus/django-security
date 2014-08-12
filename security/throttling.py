from datetime import timedelta

from django.utils import timezone

from .models import LoggedRequest
from .utils import get_client_ip
from .exception import ThrottlingException
from django.utils.unittest.compatibility import wraps


class ThrottlingValidator(object):

    def validate(self, request):
        raise NotImplemented


class PerRequestThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at):
        self.timeframe = timeframe
        self.throttle_at = throttle_at

    def validate(self, request):
        count_same_requests = LoggedRequest.objects.filter(ip=get_client_ip(request), path=request.path,
                                                       timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe))\
                                                       .count()
        if count_same_requests > self.throttle_at:
            raise ThrottlingException()


def throttling(validator):

    def decorator(function):
        def _throttling(self, request, *args, **kwargs):
            validator.validate(request)
            return function(self, request, *args, **kwargs)
        return _throttling

    return decorator