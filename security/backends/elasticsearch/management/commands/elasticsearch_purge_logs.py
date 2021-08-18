from elasticsearch_dsl import Q

from security.backends.elasticsearch.models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskInvocationLog, CeleryTaskRunLog
)

from security.backends.purge_logs import Command as PurgeLogsCommand


class Command(PurgeLogsCommand):

    models = {
        'input-request': InputRequestLog,
        'output-request': OutputRequestLog,
        'command': CommandLog,
        'celery-invocation': CeleryTaskInvocationLog,
        'celery-run': CeleryTaskRunLog,
    }

    def _clean_data(self, qs, options):
        qs.delete()

    def _get_queryset(self, model, timestamp):
        return model.search().filter(Q('range', start={'lt': timestamp}))

    def _get_qs_count(self, qs):
        return qs.count()
