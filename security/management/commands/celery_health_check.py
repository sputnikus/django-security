from django.core.management.base import BaseCommand, CommandError
from django.db.models import DurationField, ExpressionWrapper, F
from django.db.models.functions import Now
from django.utils.timezone import timedelta

from security.config import settings
from security.models import CeleryTaskLog, CeleryTaskRunLog


class Command(BaseCommand):

    help = 'Check number of waiting Celery tasks in given queue'
    messages = {
        'invalid_max_created_at_diff': 'Max created at diff must be >= 0.',
        'invalid_max_tasks_count': 'Max tasks count must be >= 0.',
        'max_created_at_diff_error': ('There is a task waiting for more than {} seconds in queue "{}" and therefore it '
                                      'is considered as overfilled.'),
        'max_tasks_count_error': ('There are more than {} waiting tasks in queue "{}" and therefore it is considered as'
                                  'overfilled.'),
        'missing_options_error': 'Specify either "--max-created-at-diff" or "--max-tasks-count".',
        'ok': 'Queue "{}" is ok.',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '-q', '--queue-name',
            default=settings.CELERY_HEALTH_CHECK_DEFAULT_QUEUE,
            dest='queue_name',
            help='Default queue name.',
            type=str,
        )
        parser.add_argument(
            '-d', '--max-created-at-diff',
            dest='max_created_at_diff',
            help='Max created at difference (in seconds).',
            type=int,
        )
        parser.add_argument(
            '-t', '--max-tasks-count',
            dest='max_tasks_count',
            help='Max count of waiting tasks.',
            type=int,
        )

    def _get_queryset(self, queue_name):
        return CeleryTaskLog.objects.filter_waiting().order_by('created_at')

    def _handle_max_created_at_diff(self, queryset, queue_name, max_created_at_diff):
        if max_created_at_diff < 0:
            raise CommandError(self.messages['invalid_max_created_at_diff'])

        if queryset.annotate(diff=ExpressionWrapper(Now() - F('created_at'), output_field=DurationField())).filter(
            diff__gt=timedelta(seconds=max_created_at_diff),
        ).exists():
            raise CommandError(self.messages['max_created_at_diff_error'].format(max_created_at_diff, queue_name))

    def _handle_max_tasks(self, queryset, queue_name, max_tasks_count):
        if max_tasks_count < 0:
            raise CommandError(self.messages['invalid_max_tasks_count'])

        if queryset.count() > max_tasks_count:
            raise CommandError(self.messages['max_tasks_count_error'].format(max_tasks_count, queue_name))

    def handle(self, **options):
        max_created_at_diff = options.get('max_created_at_diff')
        max_tasks_count = options.get('max_tasks_count')

        if max_created_at_diff is None and max_tasks_count is None:
            raise CommandError(self.messages['missing_options_error'])

        queue_name = options['queue_name']
        queryset = self._get_queryset(queue_name)

        try:
            if max_created_at_diff is not None:
                self._handle_max_created_at_diff(queryset, queue_name, max_created_at_diff)
            if max_tasks_count is not None:
                self._handle_max_tasks(queryset, queue_name, max_tasks_count)
        except CommandError as ex:
            raise ex
        else:
            self.stdout.write(self.style.SUCCESS(self.messages['ok'].format(queue_name)))
