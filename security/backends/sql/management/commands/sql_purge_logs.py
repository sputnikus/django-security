import os
import json
import gzip
import math

from datetime import datetime, time

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import utc
from django.utils.module_loading import import_string

from security.config import settings
from security.backends.sql.models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskInvocationLog, CeleryTaskRunLog
)

from io import TextIOWrapper

from security.backends.purge_logs import Command as PurgeLogsCommand


storage = import_string(settings.BACKUP_STORAGE_CLASS)()


def lazy_serialize_qs_without_pk(qs):
    def generator():
        for obj in qs.iterator():
            data = serializers.serialize('python', [obj])[0]

            del data['pk']
            yield data

    class StreamList(list):
        def __iter__(self):
            return generator()

        # according to the comment below
        def __len__(self):
            return 1

    return StreamList()


def get_querysets_by_batch(qs, batch):
    steps = math.ceil(qs.count() / batch)
    for _ in range(steps):
        yield qs[:batch]


class Command(PurgeLogsCommand):

    models = {
        'input-request': InputRequestLog,
        'output-request': OutputRequestLog,
        'command': CommandLog,
        'celery-invocation': CeleryTaskInvocationLog,
        'celery-run': CeleryTaskRunLog,
    }

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--backup', action='store', dest='backup', default=False,
                            help='Tells Django where to backup removed logs.')

    def _get_queryset(self, model, timestamp):
        return model.objects.filter(stop__lte=timestamp).order_by('stop')

    def _get_qs_count(self, qs):
        return qs.count()

    def _clean_data(self, qs, options):
        backup_path = options.get('backup')
        for timestamp in qs.datetimes('start', 'day', tzinfo=utc):
            min_timestamp = datetime.combine(timestamp, time.min).replace(tzinfo=utc)
            max_timestamp = datetime.combine(timestamp, time.max).replace(tzinfo=utc)
            qs_filtered_by_day = qs.filter(start__range=(min_timestamp, max_timestamp))

            for qs_batch in get_querysets_by_batch(qs_filtered_by_day, settings.PURGE_LOG_BACKUP_BATCH):
                self.stdout.write(
                    2 * ' ' + 'Cleaning logs for date {} ({})'.format(
                        timestamp.date(), qs_batch.count()
                    )
                )
                if backup_path:
                    log_file_name = os.path.join(backup_path, str(timestamp.date()))

                    if storage.exists('{}.json.gz'.format(log_file_name)):
                        i = 1
                        while storage.exists('{}({}).json.gz'.format(log_file_name, i)):
                            i += 1
                        log_file_name = '{}({})'.format(log_file_name, i)

                    self.stdout.write(4 * ' ' + 'generating backup file: {}.json.gz'.format(log_file_name))

                    with storage.open('{}.json.gz'.format(log_file_name), 'wb') as f:
                        with TextIOWrapper(gzip.GzipFile(filename='{}.json'.format(log_file_name),
                                                         fileobj=f, mode='wb')) as gzf:
                            json.dump(
                                lazy_serialize_qs_without_pk(qs_batch), gzf, cls=DjangoJSONEncoder, indent=5
                            )
                self.stdout.write(4 * ' ' + 'deleting logs')

                for qs_batch_to_delete in get_querysets_by_batch(qs_batch, settings.PURGE_LOG_DELETE_BATCH):
                    qs_filtered_by_day.filter(pk__in=qs_batch_to_delete).delete()
