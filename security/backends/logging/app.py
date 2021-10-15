from django.apps import AppConfig


class SecurityLoggingBackend(AppConfig):

    name = 'security.backends.logging'
    label = 'security_backends_logging'
    backend_name = 'logging'
