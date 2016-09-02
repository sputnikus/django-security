from django.conf import settings


SECURITY_DEFAULT_THROTTLING_VALIDATORS = getattr(settings, 'SECURITY_DEFAULT_THROTTLING_VALIDATORS',
                                                 'security.default_validators.validators')
SECURITY_THROTTLING_FAILURE_VIEW = getattr(settings, 'SECURITY_THROTTLING_FAILURE_VIEW',
                                           'security.views.throttling_failure_view')
SECURITY_LOG_IGNORE_IP = getattr(settings, 'SECURITY_LOG_IGNORE_IP', tuple())
SECURITY_LOG_REQUEST_BODY_LENGTH = getattr(settings, 'SECURITY_LOG_REQUEST_BODY_LENGTH', 500)
SECURITY_LOG_RESPONSE_BODY_LENGTH = getattr(settings, 'SECURITY_LOG_RESPONSE_BODY_LENGTH', 500)
SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES = getattr(settings, 'SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES', (
        'application/json', 'application/xml', 'text/xml', 'text/csv', 'text/html', 'application/xhtml+xml'
))
