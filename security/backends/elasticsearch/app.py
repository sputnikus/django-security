from django.apps import AppConfig


class SecurityElasticsearchBackend(AppConfig):

    name = 'security.backends.elasticsearch'
    label = 'security_backends_elasticsearch'
    backend_name = 'elasticsearch'
