import json
import os
import gzip

from datetime import timedelta, datetime, time

from optparse import make_option

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import utc
from django.utils.encoding import force_text

from security.models import LoggedRequest


DURATION_OPTIONS = {
    'hours': lambda amount: timezone.now() - timedelta(hours=amount),
    'days': lambda amount: timezone.now() - timedelta(days=amount),
    'weeks': lambda amount: timezone.now() - timedelta(weeks=amount),
    'months': lambda amount: timezone.now() - timedelta(days=(30 * amount)),  # 30-day month
    'years': lambda amount: timezone.now() - timedelta(weeks=(52 * amount)),  # 364-day year
}

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.'),
        make_option('--backup', action='store', dest='backup', default=False,
            help='Tells Django where to backup removing requests.'),
    )
    help = ""
    args = '[amount duration]'

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

            if os.path.isfile('%s.json.zip' % log_file_path):
                i = 0
                while os.path.isfile('%s(%s).json.zip' % (log_file_path, i)):
                    i += 1
                log_file_path = '%s(%s)' % (log_file_path, i)

            self.stdout.write(4 * ' ' + log_file_path)
            with gzip.open('%s.json.zip' % log_file_path, 'wb') as file_out:
                file_out.writelines(json.dumps(self.serialize(file_qs), cls=DjangoJSONEncoder, indent=5))

    def handle(self, amount, duration, **options):
        # Check we have the correct values
        try:
            amount = int(amount)
        except ValueError:
            self.stderr.write('Amount must be a number')
            return

        if duration[-1] != 's':  # If its not plural, make it plural
            duration_plural = '%ss' % duration
        else:
            duration_plural = duration

        if not duration_plural in DURATION_OPTIONS:
            self.stderr.write('Amount must be %s' % ', '.join(DURATION_OPTIONS))
            return

        qs = LoggedRequest.objects.filter(request_timestamp__lte=DURATION_OPTIONS[duration_plural](amount))
        count = qs.count()

        if count == 0:
            self.stdout.write('There are no requests to delete.')
            return

        if options.get('interactive'):
            confirm = raw_input('''
            You have requested a database reset.
            This will IRREVERSIBLY DESTROY any
            logged requests created before %d %s 
            ago. That is a total of %d requests.
            Are you sure you want to do this?
            Type 'yes' to continue, or 'no' to cancel: ''' % (amount, duration, count))
        else:
            confirm = 'yes'

        if confirm == 'yes':
            try:
                if options.get('backup'):
                    self.backup_to_file(qs, options.get('backup'))
                self.stdout.write('Removing data')
                qs.delete()
            except IOError as ex:
                self.stderr.write(force_text(ex))
