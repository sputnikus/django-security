from django.conf import settings

from .throttling import PerRequestThrottlingValidator

DEFAULT_THROTTLING_VALIDATORS = getattr(settings, 'AUTH_COOKIE_NAME',
                                        (
                                         PerRequestThrottlingValidator(3600, 150),  # 150 per an hour
                                         PerRequestThrottlingValidator(60, 10),  # 10 per an minute
                                         ))