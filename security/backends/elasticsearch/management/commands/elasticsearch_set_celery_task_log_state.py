import json

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from elasticsearch_dsl import Q

from security.enums import CeleryTaskRunLogState, CeleryTaskInvocationLogState
from security.backends.elasticsearch.models import CeleryTaskInvocationLog

from celery import current_app
from celery.exceptions import NotRegistered


class Command(BaseCommand):

    def handle(self, **options):
        for task in CeleryTaskInvocationLog.search().filter(Q('range', stale_at={'lt': now()})):
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                task.update(
                    state=CeleryTaskInvocationLogState.SUCCEEDED
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                task.update(
                    state=CeleryTaskInvocationLogState.FAILED
                )
            else:
                try:
                    current_app.tasks[task.name].expire_invocation(
                        task.id,
                        json.loads(task.task_args),
                        json.loads(task.task_kwargs),
                        dict(
                            start=task.start,
                            celery_task_id=task.celery_task_id,
                            stop=now(),
                            name=task.name,
                            queue_name=task.queue_name,
                        )
                    )
                except NotRegistered:
                    task.update(
                        state=CeleryTaskInvocationLogState.EXPIRED
                    )
