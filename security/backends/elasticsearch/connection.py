from elasticsearch_dsl import connections

from django.core.exceptions import ImproperlyConfigured

from security.config import settings


class ConnectionHandler:

    connection = None

    def connect(self):
        if not self.connection:
            if not settings.ELASTICSEARCH_DATABASE:
                raise ImproperlyConfigured('You must set "SECURITY_ELASTICSEARCH_DATABASE" setting')

            connection.connection = connections.create_connection(
                **settings.ELASTICSEARCH_DATABASE
            )
            self.init_documents()

    def init_documents(self):
        from security.backends.elasticsearch.models import (
            InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog
        )

        for document in InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog:
            document.init()


connection = ConnectionHandler()


def set_connection():
    connection.connect()
