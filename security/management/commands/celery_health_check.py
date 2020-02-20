from django.core.management.base import BaseCommand, CommandError

from security.config import settings
from security.models import CeleryTaskLog, CeleryTaskRunLog, CeleryTaskRunLogState


class Command(BaseCommand):

    help = 'Check number of waiting Celery tasks in given queue'
    messages = {
        'error': 'There are more than {} waiting tasks in queue "{}" and therefore it is considered as full.',
        'invalid_max_tasks_count': 'Max tasks count must be >= 0.',
        'ok': 'Queue "{}" is ok.',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '-q', '--queue_name',
            default=settings.CELERY_HEALTH_CHECK_DEFAULT_QUEUE,
            dest='queue_name',
            help='Default queue name.',
            type=str,
        )
        parser.add_argument(
            '-m', '--max-tasks-count',
            default=settings.CELERY_HEALTH_CHECK_MAX_TASKS_COUNT,
            dest='max_tasks_count',
            help='Max count of waiting tasks.',
            type=int,
        )

    def handle(self, *args, **options):
        max_tasks_count = options['max_tasks_count']
        if max_tasks_count < 0:
            raise CommandError(self.messages['invalid_max_tasks_count'])
        queue_name = options['queue_name']

        tasks = CeleryTaskLog.objects.filter(is_set_as_stale=False, queue_name=queue_name).exclude(
            celery_task_id__in=CeleryTaskRunLog.objects.filter(
                state__in={
                    CeleryTaskRunLogState.ACTIVE,
                    CeleryTaskRunLogState.EXPIRED,
                    CeleryTaskRunLogState.FAILED,
                    CeleryTaskRunLogState.SUCCEEDED,
                },
            ).values('celery_task_id'),
        )

        if tasks.count() > max_tasks_count:
            raise CommandError(self.messages['error'].format(max_tasks_count, queue_name))
        else:
            self.stdout.write(self.style.SUCCESS(self.messages['ok'].format(queue_name)))
