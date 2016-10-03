import json
import os
import gzip

from six.moves import input

from datetime import timedelta, datetime, time

from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import utc
from django.utils.encoding import force_text, force_bytes

from security.models import InputLoggedRequest, OutputLoggedRequest


UNIT_OPTIONS = {
    'h': lambda amount: timezone.now() - timedelta(hours=amount),
    'd': lambda amount: timezone.now() - timedelta(days=amount),
    'w': lambda amount: timezone.now() - timedelta(weeks=amount),
    'm': lambda amount: timezone.now() - timedelta(days=(30 * amount)),  # 30-day month
    'y': lambda amount: timezone.now() - timedelta(weeks=(52 * amount)),  # 364-day year
}


class Command(BaseCommand):

    help = ""
    args = '[amount duration]'

    def add_arguments(self, parser):
        parser.add_argument('--expiration', action='store', dest='expiration',
                            help='Set the timedelta from requestss will be removed.', required=True)
        parser.add_argument('--noinput', action='store_false', dest='interactive', default=True,
                            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument('--backup', action='store', dest='backup', default=False,
                            help='Tells Django where to backup removing requests.')
        parser.add_argument('--type', action='store', dest='type', default='input',
                            help='Tells Django what type of requests shoud be logged (input/output).')

    def serialize(self, qs):
        data = serializers.serialize('python', qs)

        for obj_data in data:
            del obj_data['pk']
        return data

    def backup_to_file(self, qs, path):
        self.stdout.write('Backup old requests')

        for timestamp in qs.datetimes('request_timestamp', 'day'):
            min_timestamp = datetime.combine(timestamp, time.min).replace(tzinfo=utc)
            max_timestamp = datetime.combine(timestamp, time.max).replace(tzinfo=utc)
            file_qs = qs.filter(request_timestamp__range=(min_timestamp, max_timestamp))

            log_file_path = os.path.abspath(os.path.join(path, force_text(timestamp.date())))

            if os.path.isfile('{}.json.zip'.format(log_file_path)):
                i = 0
                while os.path.isfile('{}({}).json.zip'.format(log_file_path, i)):
                    i += 1
                log_file_path = '{}({})'.format(log_file_path, i)

            self.stdout.write(4 * ' ' + log_file_path)
            with gzip.open('{}.json.zip'.format(log_file_path), 'wb') as file_out:
                file_out.write(force_bytes(json.dumps(self.serialize(file_qs), cls=DjangoJSONEncoder, indent=5)))

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

        if type == 'input':
            model = InputLoggedRequest
        elif type == 'output':
            model = OutputLoggedRequest
        else:
            raise CommandError('Type can be only input or output')

        qs = model.objects.filter(request_timestamp__lte=UNIT_OPTIONS[unit](amount))

        if qs.count() == 0:
            self.stdout.write('There are no requests to delete.')
        else:
            if options.get('interactive'):
                confirm = input('''
                You have requested a database reset.
                This will IRREVERSIBLY DESTROY any
                logged requests created before {} {}
                ago. That is a total of {} requests.
                Are you sure you want to do this?
                Type 'yes' to continue, or 'no' to cancel: '''.format(amount, duration, count))
            else:
                confirm = 'yes'

            if confirm == 'yes':
                try:
                    if options.get('backup'):
                        self.backup_to_file(qs, options.get('backup'))
                    self.stdout.write('Removing data')
                    qs.delete()
                except IOError as ex:
                    raise CommandError(force_text(ex))
