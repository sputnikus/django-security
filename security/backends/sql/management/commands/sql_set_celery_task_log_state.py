from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from chamber.shortcuts import change_and_save

from security.enums import CeleryTaskRunLogState, CeleryTaskInvocationLogState
from security.backends.sql.models import CeleryTaskInvocationLog

from celery import current_app
from celery.exceptions import NotRegistered


class Command(BaseCommand):

    def handle(self, **options):
        for task in CeleryTaskInvocationLog.objects.filter_processing(stale_at__lt=now()).iterator():
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                change_and_save(
                    task,
                    state=CeleryTaskInvocationLogState.SUCCEEDED,
                    stop=task_last_run.stop
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                change_and_save(
                    task,
                    state=CeleryTaskInvocationLogState.FAILED,
                    stop=task_last_run.stop
                )
            else:
                try:
                    current_app.tasks[task.name].expire_invocation(
                        task.id,
                        task.task_args,
                        task.task_kwargs,
                        dict(
                            start=task.start,
                            celery_task_id=task.celery_task_id,
                            stop=now(),
                            name=task.name,
                            queue_name=task.queue_name,
                        )
                    )
                except NotRegistered:
                    change_and_save(
                        task,
                        state=CeleryTaskInvocationLogState.EXPIRED,
                        stop=now()
                    )
