from datetime import timedelta

from ipware.ip import get_ip

from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.urls import resolve

from .exception import ThrottlingException
from .models import InputLoggedRequest, InputLoggedRequestType


class ThrottlingValidator:

    def __init__(self, timeframe, throttle_at, description):
        self.timeframe = timeframe
        self.throttle_at = throttle_at
        self.description = description

    def validate(self, request):
        if not getattr(settings, 'TURN_OFF_THROTTLING', False) and not self._validate(request):
            raise ThrottlingException(self.description)

    def _validate(self, request):
        raise NotImplemented

    def __repr__(self):
        return '<{} (timeframe={}, throttle_at={}, description={})>'.format(
            self.__class__.__name__, self.timeframe, self.throttle_at, self.description
        )


class PerRequestThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('Slow down')):
        super(PerRequestThrottlingValidator, self).__init__(timeframe, throttle_at, description)

    def _validate(self, request):
        try:
            qs = InputLoggedRequest.objects.filter(
                slug=resolve(request.path_info, getattr(request, 'urlconf', None)).view_name
            )
        except Resolver404:
            qs = InputLoggedRequest.objects.filter(slug__isnull=True)

        count_same_requests = qs.filter(
            ip=get_ip(request), path=request.path,
            request_timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe),
            method=request.method.upper()
        ).count()
        return count_same_requests <= self.throttle_at


class LoginThrottlingValidator(ThrottlingValidator):

    def _validate(self, request):
        count_same_requests = InputLoggedRequest.objects.filter(
            ip=get_ip(request), path=request.path,
            request_timestamp__gte=timezone.now() - timedelta(seconds=self.timeframe),
            type=self.type).count()
        return count_same_requests <= self.throttle_at


class UnsuccessfulLoginThrottlingValidator(LoginThrottlingValidator):

    type = InputLoggedRequestType.UNSUCCESSFUL_LOGIN_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('Too many login attempts')):
        super().__init__(timeframe, throttle_at, description)


class SuccessfulLoginThrottlingValidator(LoginThrottlingValidator):

    type = InputLoggedRequestType.SUCCESSFUL_LOGIN_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('You have logged in too many times')):
        super().__init__(timeframe, throttle_at, description)


class UnSuccessfulTwoFactorCodeVerificationThrottlingValidator(LoginThrottlingValidator):

    type = InputLoggedRequestType.UNSUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('Too many login attempts')):
        super().__init__(timeframe, throttle_at, description)


class SuccessfulTwoFactorCodeVerificationThrottlingValidator(LoginThrottlingValidator):

    type = InputLoggedRequestType.SUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('You have logged in too many times')):
        super().__init__(timeframe, throttle_at, description)
