import os
import json
import gzip
import math

from datetime import datetime, time, timedelta

from elasticsearch_dsl import Q

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand
from django.utils.timezone import now, utc
from django.utils.module_loading import import_string

from security.config import settings
from security.backends.elasticsearch.models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskInvocationLog, CeleryTaskRunLog
)

from io import TextIOWrapper


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


def get_querysets_by_batch(qs, batch):
    steps = math.ceil(qs.count() / batch)
    for _ in range(steps):
        yield qs[:batch]


class Command(BaseCommand):

    models = {
        'input-request': InputRequestLog,
        'output-request': OutputRequestLog,
        'command': CommandLog,
        'celery-invocation': CeleryTaskInvocationLog,
        'celery-run': CeleryTaskRunLog,
    }

    def add_arguments(self, parser):
        parser.add_argument('--type', action='store', dest='type', default='input-request',
                            help='Tells Django what type of requests should be removed '
                                 '({}).'.format('/'.join(self.models.keys())))
        parser.add_argument('--expiration', action='store', dest='expiration',
                            help='Sets the timedelta from which logs will be removed.', required=True)
        parser.add_argument('--noinput', action='store_false', dest='interactive', default=True,
                            help='Tells Django to NOT prompt the user for input of any kind.')

    def clean_data(self, qs):
        qs.delete()

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
        qs = model.search().filter(Q('range', start={'lt': UNIT_OPTIONS[unit](amount)})).sort('start')

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
                    sqs.delete()
                except IOError as ex:
                    self.stderr.write(str(ex))

    def get_model(self, type):
        model = self.models.get(type)
        if model:
            return model
        else:
            raise CommandError('Type can be only one of "{}"'.format('/'.join(self.models.keys())))
