from uuid import uuid4

from django.test.utils import override_settings, TestContextDecorator

from .models import CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog, InputRequestLog, OutputRequestLog


class store_elasticsearch_log(override_settings):

    def __init__(self):
        super().__init__(SECURITY_BACKENDS=('elasticsearch',), SECURITY_ELASTICSEARCH_AUTO_REFRESH=True)

    def enable(self):
        super().enable()
        for document_class in (CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog,
                               InputRequestLog, OutputRequestLog):
            document_class._index._name = f'{uuid4()}.{document_class._index._name}'
            document_class.init()

    def disable(self):
        super().disable()
        for document_class in (CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog,
                               InputRequestLog, OutputRequestLog):
            document_class._index.delete()
            document_class._index._name = document_class._index._name.split('.', 1)[1]
