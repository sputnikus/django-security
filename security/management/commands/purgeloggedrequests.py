from django.core.management.base import CommandError

from security.models import InputLoggedRequest, OutputLoggedRequest
from security.utils import PurgeLogsBaseCommand


class Command(PurgeLogsBaseCommand):

    timestamp_field = 'request_timestamp'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--type', action='store', dest='type', default='input',
                            help='Tells Django what type of requests should be removed (input/output).')

    def handle(self, expiration, type, **options):
        self.type = type
        super().handle(expiration, **options)

    def get_model(self):
        if self.type == 'input':
            return InputLoggedRequest
        elif self.type == 'output':
            return OutputLoggedRequest
        else:
            raise CommandError('Type can be only input or output')
