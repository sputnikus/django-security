import os
import json
import gzip

from datetime import datetime, time, timedelta

from django.core import serializers
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand
from django.utils.timezone import now, utc
from django.utils.module_loading import import_string
from django.utils.encoding import force_bytes, force_text

from security.config import settings
from security.models import InputLoggedRequest, OutputLoggedRequest, CommandLog, CeleryTaskLog, CeleryTaskRunLog

from io import BytesIO, TextIOWrapper


storage = import_string(settings.BACKUP_STORAGE_CLASS)()


UNIT_OPTIONS = {
    'h': lambda amount: now() - timedelta(hours=amount),
    'd': lambda amount: now() - timedelta(days=amount),
    'w': lambda amount: now() - timedelta(weeks=amount),
    'm': lambda amount: now() - timedelta(days=(30 * amount)),  # 30-day month
    'y': lambda amount: now() - timedelta(weeks=(52 * amount)),  # 364-day year
}


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


class Command(BaseCommand):

    models = {
        'input-request': InputLoggedRequest,
        'output-request': OutputLoggedRequest,
        'command': CommandLog,
        'celery': CeleryTaskLog,
        'celery-run': CeleryTaskRunLog,
    }

    def add_arguments(self, parser):
        parser.add_argument('--type', action='store', dest='type', default='input',
                            help='Tells Django what type of requests should be removed '
                                 '({}).'.format('/'.join(self.models.keys())))
        parser.add_argument('--expiration', action='store', dest='expiration',
                            help='Sets the timedelta from which logs will be removed.', required=True)
        parser.add_argument('--noinput', action='store_false', dest='interactive', default=True,
                            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument('--backup', action='store', dest='backup', default=False,
                            help='Tells Django where to backup removed logs.')

    def backup_logs_and_clean_data(self, qs, backup_path):
        for timestamp in qs.datetimes('created_at', 'day', tzinfo=utc):
            min_timestamp = datetime.combine(timestamp, time.min).replace(tzinfo=utc)
            max_timestamp = datetime.combine(timestamp, time.max).replace(tzinfo=utc)
            qs_filtered_by_day = qs.filter(created_at__range=(min_timestamp, max_timestamp))
            if backup_path:
                log_file_name = os.path.join(backup_path, str(timestamp.date()))

                if storage.exists('{}.json.gz'.format(log_file_name)):
                    i = 1
                    while storage.exists('{}({}).json.gz'.format(log_file_name, i)):
                        i += 1
                    log_file_name = '{}({})'.format(log_file_name, i)

                self.stdout.write(4 * ' ' + 'generate backup file: {}.json.gz'.format(log_file_name))

                with storage.open('{}.json.gz'.format(log_file_name), 'wb') as f:
                    with TextIOWrapper(gzip.GzipFile(filename='{}.json'.format(log_file_name),
                                                     fileobj=f, mode='wb')) as gzf:
                        json.dump(
                            lazy_serialize_qs_without_pk(qs_filtered_by_day), gzf, cls=DjangoJSONEncoder, indent=5
                        )
            self.stdout.write(4 * ' ' + 'clean logs for day {}'.format(timestamp.date()))
            qs_filtered_by_day.delete()

    def handle(self, expiration, type, **options):
        # Check we have the correct values
        unit = expiration[-1]
        amount = expiration[0:-1]
        try:
            amount = int(amount)
        except ValueError:
            raise CommandError('Invalid expiration format')

        if unit not in UNIT_OPTIONS:
            raise CommandError('Invalid expiration format')

        model = self.get_model(type)
        qs = model.objects.filter(created_at__lte=UNIT_OPTIONS[unit](amount))

        if qs.count() == 0:
            self.stdout.write('There are no logs to delete.')
        else:
            if options.get('interactive'):
                confirm = input('''
                   You have requested a database reset.
                   This will IRREVERSIBLY DESTROY any
                   logs created before {} {}
                   ago. That is a total of {} logs.
                   Are you sure you want to do this?
                   Type 'yes' to continue, or 'no' to cancel: '''.format(amount, unit, qs.count()))
            else:
                confirm = 'yes'

            if confirm == 'yes':
                try:
                    self.stdout.write('Clean data')
                    self.backup_logs_and_clean_data(qs, options.get('backup'))
                except IOError as ex:
                    self.stderr.write(force_text(ex))

    def get_model(self, type):
        model = self.models.get(type)
        if model:
            return model
        else:
            raise CommandError('Type can be only one of "{}"'.format('/'.join(self.models.keys())))
