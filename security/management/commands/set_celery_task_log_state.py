from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from security.enums import CeleryTaskRunLogState, CeleryTaskLogState
from security.models import CeleryTaskLog

from celery import current_app
from celery.exceptions import NotRegistered


class Command(BaseCommand):

    def handle(self, **options):
        for task in CeleryTaskLog.objects.filter_processing(stale__lt=timezone.now()).iterator():
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                task.change_and_save(
                    state=CeleryTaskLogState.SUCCEEDED
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                task.change_and_save(
                    state=CeleryTaskLogState.FAILED
                )
            else:
                try:
                    current_app.tasks[task.name].expire_task(task)
                except NotRegistered:
                    task.change_and_save(
                        state=CeleryTaskLogState.EXPIRED
                    )
