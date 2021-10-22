import json

from django.utils.timezone import now

from celery import current_app
from celery.exceptions import NotRegistered

from elasticsearch_dsl import Q

from security.config import settings
from security.enums import (
    RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)
from security.backends.writer import BaseBackendWriter

from .app import SecurityElasticsearchBackend
from .models import (
    InputRequestLog, OutputRequestLog, CommandLog, CeleryTaskRunLog, CeleryTaskInvocationLog, get_key_from_object,
    get_response_state, get_log_model_from_logger_name
)


class ElasticsearchBackendWriter(BaseBackendWriter):

    def input_request_started(self, logger):
        related_objects = [
            get_key_from_object(related_object) for related_object in logger.related_objects
        ]

        input_request_log = InputRequestLog(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=RequestLogState.INCOMPLETE,
            related_objects=related_objects,
            **logger.data
        )
        input_request_log.meta.id = logger.id
        if logger.parent_with_id:
            input_request_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)

        logger.backend_logs.elasticsearch = input_request_log
        input_request_log.save()

    def input_request_finished(self, logger):
        input_request_log = logger.backend_logs.elasticsearch
        input_request_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=get_response_state(logger.data['response_code']),
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def input_request_error(self, logger):
        input_request_log = logger.backend_logs.elasticsearch
        input_request_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def output_request_started(self, logger):
        related_objects = [
            get_key_from_object(related_object) for related_object in logger.related_objects
        ]
        output_request_log = OutputRequestLog(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=RequestLogState.INCOMPLETE,
            related_objects=related_objects,
            update_only_changed_fields=True,
            **logger.data
        )
        output_request_log.meta.id = logger.id
        if logger.parent_with_id:
            output_request_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
        logger.backend_logs.elasticsearch = output_request_log
        output_request_log.save()

    def output_request_finished(self, logger):
        output_request_log = logger.backend_logs.elasticsearch
        output_request_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=get_response_state(logger.data['response_code']),
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def output_request_error(self, logger):
        output_request_log = logger.backend_logs.elasticsearch
        output_request_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=RequestLogState.ERROR,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def command_started(self, logger):
        related_objects = [
            get_key_from_object(related_object) for related_object in logger.related_objects
        ]
        command_log = CommandLog(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CommandState.ACTIVE,
            related_objects=related_objects,
            **logger.data
        )
        command_log.meta.id = logger.id
        if logger.parent_with_id:
            command_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
        logger.backend_logs.elasticsearch = command_log
        command_log.save()

    def command_output_updated(self, logger):
        command_log = logger.backend_logs.elasticsearch
        command_log.update(
            slug=logger.slug,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def command_finished(self, logger):
        command_log = logger.backend_logs.elasticsearch
        command_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CommandState.SUCCEEDED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def command_error(self, logger):
        command_log = logger.backend_logs.elasticsearch
        command_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CommandState.FAILED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def celery_task_invocation_started(self, logger):
        related_objects = [
            get_key_from_object(related_object) for related_object in logger.related_objects
        ]
        celery_task_invocation_log = CeleryTaskInvocationLog(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskInvocationLogState.WAITING,
            related_objects=related_objects,
            **logger.data
        )
        celery_task_invocation_log.meta.id = logger.id
        if logger.parent_with_id:
            celery_task_invocation_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
        logger.backend_logs.elasticsearch = celery_task_invocation_log
        celery_task_invocation_log.save()

    def celery_task_invocation_triggered(self, logger):
        celery_task_invocation_log = logger.backend_logs.elasticsearch
        celery_task_invocation_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskInvocationLogState.TRIGGERED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def celery_task_invocation_ignored(self, logger):
        celery_task_invocation_log = logger.backend_logs.elasticsearch
        celery_task_invocation_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskInvocationLogState.IGNORED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def celery_task_invocation_timeout(self, logger):
        celery_task_invocation_log = logger.backend_logs.elasticsearch
        celery_task_invocation_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskInvocationLogState.TIMEOUT,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def celery_task_invocation_expired(self, logger):
        celery_task_invocation_log = CeleryTaskInvocationLog.get(id=logger.id)
        celery_task_invocation_log.update(
            slug=logger.slug,
            state=CeleryTaskInvocationLogState.EXPIRED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )
        if celery_task_invocation_log.celery_task_id:
            CeleryTaskRunLog._index.refresh()
            celery_task_run_log_qs = CeleryTaskRunLog.search().filter(
                Q('term', celery_task_id=celery_task_invocation_log.celery_task_id)
                & Q('term', state=CeleryTaskRunLogState.ACTIVE.name)
            )
            for celery_task_run in celery_task_run_log_qs:
                celery_task_run.update(
                    state=CeleryTaskRunLogState.EXPIRED,
                    stop=logger.data['stop']
                )

    def celery_task_run_started(self, logger):
        related_objects = [
            get_key_from_object(related_object) for related_object in logger.related_objects
        ]
        celery_task_run_log = CeleryTaskRunLog(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.ACTIVE,
            related_objects=related_objects,
            **logger.data
        )
        celery_task_run_log.meta.id = logger.id
        if logger.parent_with_id:
            celery_task_run_log.parent_log = '{}|{}'.format(logger.parent_with_id.name, logger.parent_with_id.id)
        logger.backend_logs.elasticsearch = celery_task_run_log
        celery_task_run_log.save()

    def celery_task_run_succeeded(self, logger):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.SUCCEEDED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

        CeleryTaskInvocationLog._index.refresh()
        celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
            'term', celery_task_id=celery_task_run_log.celery_task_id
        ).query(
            Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
            | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
            | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
        )
        for celery_task_invocation in celery_task_invocations_qs:
            celery_task_invocation.update(
                state=CeleryTaskInvocationLogState.SUCCEEDED,
                stop=logger.data['stop'],
                refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
                update_only_changed_fields=True,
            )

    def celery_task_run_failed(self, logger):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.FAILED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

        CeleryTaskInvocationLog._index.refresh()
        celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
            'term', celery_task_id=celery_task_run_log.celery_task_id
        ).query(
            Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
            | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
            | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
        )
        for celery_task_invocation in celery_task_invocations_qs:
            celery_task_invocation.update(
                state=CeleryTaskInvocationLogState.FAILED,
                refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
                stop=logger.data['stop'],
                update_only_changed_fields=True,
            )

    def celery_task_run_retried(self, logger):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            extra_data=logger.extra_data,
            state=CeleryTaskRunLogState.RETRIED,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data
        )

    def celery_task_run_output_updated(self, logger):
        celery_task_run_log = logger.backend_logs.elasticsearch
        celery_task_run_log.update(
            slug=logger.slug,
            refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            update_only_changed_fields=True,
            **logger.data,
        )

    def set_stale_celery_task_log_state(self):
        processsing_stale_tasks = CeleryTaskInvocationLog.search().filter(
            Q('range', stale_at={'lt': now()}) & Q(
                Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
                | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
                | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
            )
        )

        for task in processsing_stale_tasks:
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                task.update(
                    state=CeleryTaskInvocationLogState.SUCCEEDED,
                    stop=task_last_run.stop,
                    update_only_changed_fields=True
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                task.update(
                    state=CeleryTaskInvocationLogState.FAILED,
                    stop=task_last_run.stop,
                    update_only_changed_fields=True
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
                        state=CeleryTaskInvocationLogState.EXPIRED,
                        stop=now(),
                        update_only_changed_fields=True
                    )

    def clean_logs(self, type, timestamp, backup_path, stdout):
        qs = get_log_model_from_logger_name(type).search().filter(Q('range', start={'lt': timestamp}))
        stdout.write(f'  Removing "{qs.count()}" logs')
        qs.delete()
