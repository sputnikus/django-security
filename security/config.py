from django.conf import settings

from .throttling import PerRequestThrottlingValidator, UnsuccessfulLoginThrottlingValidator, SuccessfulLoginThrottlingValidator

DEFAULT_THROTTLING_VALIDATORS = getattr(settings, 'AUTH_COOKIE_NAME',
                                        (
                                         PerRequestThrottlingValidator(3600, 150),  # 150 per an hour
                                         PerRequestThrottlingValidator(60, 10),  # 10 per an minute
                                         UnsuccessfulLoginThrottlingValidator(60, 2),
                                         UnsuccessfulLoginThrottlingValidator(10 * 60, 10),
                                         SuccessfulLoginThrottlingValidator(60, 2),
                                         SuccessfulLoginThrottlingValidator(10 * 60, 10),
                                         ))
THROTTLING_FAILURE_VIEW = getattr(settings, 'THROTTLING_FAILURE_VIEW', 'security.views.throttling_failure_view')

MAX_LOGGED_REQUESTS = 1000