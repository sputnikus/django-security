from django.conf import settings


DEFAULT_THROTTLING_VALIDATORS = getattr(settings, 'DEFAULT_THROTTLING_VALIDATORS', 'security.default_validators')
THROTTLING_FAILURE_VIEW = getattr(settings, 'THROTTLING_FAILURE_VIEW', 'security.views.throttling_failure_view')
LOG_IGNORE_IP = getattr(settings, 'LOG_IGNORE_IP', tuple())
LOG_REQUEST_BODY_LENGTH = getattr(settings, 'LOG_REQUEST_BODY_LENGTH', 500)
