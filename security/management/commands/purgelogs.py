from django.core.management.base import CommandError

from security.models import InputLoggedRequest, OutputLoggedRequest, CommandLog, CeleryTaskLog
from security.utils import PurgeLogsBaseCommand


class Command(PurgeLogsBaseCommand):

    timestamp_field = 'created_at'

    models = {
        'input-request': InputLoggedRequest,
        'output-request': OutputLoggedRequest,
        'command': CommandLog,
        'celery': CeleryTaskLog
    }

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--type', action='store', dest='type', default='input',
                            help='Tells Django what type of requests should be removed '
                                 '(input-request/output-request/command/celery).')

    def handle(self, expiration, type, **options):
        self.type = type
        super().handle(expiration, **options)

    def get_model(self):
        model = self.models.get(self.type)
        if model:
            return model
        else:
            raise CommandError('Type can be only input-request, output-request, command or celery')
