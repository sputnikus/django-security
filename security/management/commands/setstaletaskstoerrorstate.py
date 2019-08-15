from django.core.management.base import BaseCommand

from security.models import CeleryTaskLog, CeleryTaskLogState


class Command(BaseCommand):

    def handle(self, **options):
        stale_tasks = CeleryTaskLog.objects.filter_stale()
        if stale_tasks.exists():
            stale_tasks.update(
                state=CeleryTaskLogState.FAILED,
                error_message='Task execution was expired by command'
            )
            self.stderr.write(
                'Some tasks were too old and were set to error state. '
                'List of their IDs is:\n{}'.format(
                    ', '.join((str(v) for v in stale_tasks.values_list('pk', flat=True)))
                )
            )
        else:
            self.stdout.write('No stale tasks were found.')
