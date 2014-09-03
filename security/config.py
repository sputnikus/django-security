from django.conf import settings


DEFAULT_THROTTLING_VALIDATORS = getattr(settings, 'DEFAULT_THROTTLING_VALIDATORS', 'security.default_validators')
THROTTLING_FAILURE_VIEW = getattr(settings, 'THROTTLING_FAILURE_VIEW', 'security.views.throttling_failure_view')

MAX_LOGGED_REQUESTS = getattr(settings, 'MAX_LOGGED_REQUESTS', 10000)
