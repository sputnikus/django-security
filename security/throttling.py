from datetime import timedelta

import inspect

from functools import wraps

from django.utils import timezone
from django.utils.translation import ugettext as _
from django.utils.decorators import available_attrs

from .models import LoggedRequest
from .utils import get_client_ip
from .exception import ThrottlingException


class ThrottlingValidator(object):

    def __init__(self, timeframe, throttle_at, description):
        self.timeframe = timeframe
        self.throttle_at = throttle_at
        self.description = description

    def validate(self, request):
        if not self._validate(request):
            raise ThrottlingException(self.description)

    def _validate(self, request):
        raise NotImplemented


class PerRequestThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('Slow down')):
        super(PerRequestThrottlingValidator, self).__init__(timeframe, throttle_at, description)

    def _validate(self, request):
        count_same_requests = LoggedRequest.objects.filter(ip=get_client_ip(request), path=request.path,
                                                           timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe),
                                                           method=request.method.upper())\
                                                           .count()
        return count_same_requests <= self.throttle_at


class UnsuccessfulLoginThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('Too many login attempts')):
        super(UnsuccessfulLoginThrottlingValidator, self).__init__(timeframe, throttle_at, description)

    def _validate(self, request):
        count_same_requests = LoggedRequest.objects.filter(ip=get_client_ip(request), path=request.path,
                                                       timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe),
                                                       type=LoggedRequest.UNSUCCESSFUL_LOGIN_REQUEST)\
                                                       .count()
        return count_same_requests <= self.throttle_at


class SuccessfulLoginThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('You are logged too much times')):
        super(SuccessfulLoginThrottlingValidator, self).__init__(timeframe, throttle_at, description)

    def _validate(self, request):
        count_same_requests = LoggedRequest.objects.filter(ip=get_client_ip(request), path=request.path,
                                                       timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe),
                                                       type=LoggedRequest.SUCCESSFUL_LOGIN_REQUEST)\
                                                       .count()
        return count_same_requests <= self.throttle_at


def throttling(validator):
    """
    Adds throttling validator to a function.
    """
    def decorator(view_func):
        def _throttling(self, request, *args, **kwargs):
            validator.validate(request)
            return view_func(self, request, *args, **kwargs)
        return wraps(view_func, assigned=available_attrs(view_func))(_throttling)

    return decorator


def throttling_all(klass):
    """
    Adds throttling validator to a class.
    """
    dispatch = getattr(klass, 'dispatch')
    setattr(klass, 'dispatch', throttling()(dispatch))
    return klass


def throttling_exempt():
    """
    Marks a function as being exempt from the throttling protection.
    """
    def decorator(view_func):
        def _throttling_exempt(*args, **kwargs):
            return view_func(*args, **kwargs)
        _throttling_exempt.throttling_exempt = True
        return wraps(view_func, assigned=available_attrs(view_func))(_throttling_exempt)

    return decorator


def throttling_exempt_all(klass):
    """
    Marks a class as being exempt from the throttling protection.
    """
    dispatch = getattr(klass, 'dispatch')
    setattr(klass, 'dispatch', throttling_exempt()(dispatch))
    return klass
