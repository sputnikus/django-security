from elasticsearch_dsl import connections

from django.core.exceptions import ImproperlyConfigured

from security.config import settings


if not settings.ELASTICSEARCH_DATABASE:
    raise ImproperlyConfigured('You must set "SECURITY_ELASTICSEARCH_DATABASE" setting')


connections.create_connection(
    **settings.ELASTICSEARCH_DATABASE
)

default_app_config = 'security.backends.elasticsearch.app.SecurityElasticsearchBackend'
