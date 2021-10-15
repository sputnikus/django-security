from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.urls import resolve

from ipware.ip import get_client_ip

from security.enums import InputRequestSlug
from security.throttling.validators import ThrottlingValidator
from security.throttling.exception import ThrottlingException

from .models import InputRequestLog


class PerRequestThrottlingValidator(ThrottlingValidator):

    def __init__(self, timeframe, throttle_at, description=_('Slow down')):
        super().__init__(timeframe, throttle_at, description)

    def _validate(self, request):
        try:
            qs = InputRequestLog.objects.filter(
                view_slug=resolve(request.path_info, getattr(request, 'urlconf', None)).view_name
            )
        except Resolver404:
            qs = InputRequestLog.objects.filter(view_slug__isnull=True)

        count_same_requests = qs.filter(
            ip=get_client_ip(request)[0],
            path=request.path,
            start__gte=timezone.now() - timedelta(seconds=self.timeframe),
            method=request.method.upper()
        ).count()
        return count_same_requests <= self.throttle_at


class LoginThrottlingValidator(ThrottlingValidator):

    slug = None

    def _validate(self, request):
        count_same_requests = InputRequestLog.objects.filter(
            ip=get_client_ip(request)[0],
            path=request.path,
            start__gte=timezone.now() - timedelta(seconds=self.timeframe),
            slug=self.slug
        ).count()
        return count_same_requests <= self.throttle_at


class UnsuccessfulLoginThrottlingValidator(LoginThrottlingValidator):

    slug = InputRequestSlug.UNSUCCESSFUL_LOGIN_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('Too many login attempts')):
        super().__init__(timeframe, throttle_at, description)


class SuccessfulLoginThrottlingValidator(LoginThrottlingValidator):

    type = InputRequestSlug.SUCCESSFUL_LOGIN_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('You have logged in too many times')):
        super().__init__(timeframe, throttle_at, description)


class UnSuccessfulTwoFactorCodeVerificationThrottlingValidator(LoginThrottlingValidator):

    type = InputRequestSlug.UNSUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('Too many login attempts')):
        super().__init__(timeframe, throttle_at, description)


class SuccessfulTwoFactorCodeVerificationThrottlingValidator(LoginThrottlingValidator):

    type = InputRequestSlug.SUCCESSFUL_2FA_CODE_VERIFICATION_REQUEST

    def __init__(self, timeframe, throttle_at, description=_('You have logged in too many times')):
        super().__init__(timeframe, throttle_at, description)
