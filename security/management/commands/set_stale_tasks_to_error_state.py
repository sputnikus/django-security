from django.core.management.base import BaseCommand

from security.models import CeleryTaskLog

from celery import current_app


class Command(BaseCommand):

    def handle(self, **options):
        for task in CeleryTaskLog.objects.filter_stale():
            current_app.tasks[task.name].expire_task(task)
