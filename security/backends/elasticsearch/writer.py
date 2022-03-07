import os
import json
import gzip
import math
import logging

from enum import Enum

from io import TextIOWrapper

from datetime import datetime, time, timedelta

from django.utils.timezone import now, utc
from django.utils.module_loading import import_string
from django.core.serializers.json import DjangoJSONEncoder

from celery import current_app
from celery.exceptions import NotRegistered

from elasticsearch import ConflictError
from elasticsearch_dsl import Q

from security.config import settings
from security.enums import (
    RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)
from security.backends.writer import BaseBackendWriter

from .models import (
    CeleryTaskRunLog, CeleryTaskInvocationLog, get_key_from_content_type_object_id_and_model_db, get_response_state,
    get_log_model_from_logger_name, get_object_triple_from_key, logger_name_to_log_model, get_index_name
)


logstash_logger = logging.getLogger('security.logstash')


def lazy_serialize_qs_without_pk(qs):
    def generator():
        for obj in qs:
            yield obj.to_dict()

    class StreamList(list):
        def __iter__(self):
            return generator()

        def __len__(self):
            return 1

    return StreamList()


def get_querysets_by_batch(qs, batch):
    steps = math.ceil(qs.count() / batch)
    for step in range(steps):
        yield qs[step * batch:(step+1) * batch]


class BaseElasticsearchDataWriter:

    def _get_related_object_keys(self, logger):
        return [
            get_key_from_content_type_object_id_and_model_db(content_type_pk, object_pk, model_db)
            for model_db, content_type_pk, object_pk in logger.related_objects
        ]

    def _get_index_data(self, index):
        return {
            field_name: (
                getattr(index, field_name).to_dict() if description['type'] == 'object' else getattr(index, field_name)
            )
            for field_name, description in index._doc_type.mapping.properties.to_dict()['properties'].items()
        }

    def _update_data(self, data):
        data = dict(data)
        start = data.get('start')
        stop = data.get('stop')
        if start and stop:
            data['time'] = (stop - start).total_seconds()
        return data

    def update_index(self, index, **updated_data):
        raise NotImplementedError

    def create_or_update_index_from_logger(self, logger, is_last=False, **extra_data):
        raise NotImplementedError


class DirectElasticsearchDataWriter(BaseElasticsearchDataWriter):

    def update_index(self, index, **updated_data):
        try:
            data = self._get_index_data(index)
            data.update(updated_data)
            index.update(
                **self._update_data(data),
                update_only_changed_fields=True,
                retry_on_conflict=1,
                refresh=settings.ELASTICSEARCH_AUTO_REFRESH,
            )
        except ConflictError:
            # conflict errors are ignored, celery task invocation was changed with another process
            pass

    def _create_index_from_logger(self, logger, **extra_data):
        index_class = get_log_model_from_logger_name(logger.name)
        index = index_class(
            slug=logger.slug,
            release=logger.release,
            related_objects=self._get_related_object_keys(logger),
            extra_data=logger.extra_data,
            parent_log=logger.parent_key,
            **extra_data,
            **self._update_data(logger.data)
        )
        index.meta.id = logger.id
        index.save()
        logger.backend_logs.elasticsearch_index = index

    def _update_index_from_logger(self, logger, **extra_data):
        self.update_index(logger.backend_logs.elasticsearch_index, **dict(
            slug=logger.slug,
            related_objects=self._get_related_object_keys(logger),
            extra_data=logger.extra_data,
            **extra_data,
            **self._update_data(logger.data)
        ))

    def create_or_update_index_from_logger(self, logger, is_last=True, **extra_data):
        if 'elasticsearch_index' in logger.backend_logs:
            self._update_index_from_logger(logger, **extra_data)
        else:
            self._create_index_from_logger(logger, **extra_data)


class LogstashElasticsearchDataWriter(BaseElasticsearchDataWriter):

    MAX_ELASTICSEARCH_VERSION = 9999

    def _serialize_data(self, data):
        serialized_data = {}
        for k, v in data.items():
            if isinstance(v, Enum):
                serialized_data[k] = v.name
            elif isinstance(v, (list, dict, tuple)) and k not in {'extra_data', 'related_objects'}:
                serialized_data[k] = json.dumps(v, cls=DjangoJSONEncoder)
            else:
                serialized_data[k] = v
        return json.dumps(serialized_data, cls=DjangoJSONEncoder)

    def _get_log_message(self, logger_id, logger_name, version, data):
        return f'{get_index_name(logger_name)} {version} {logger_id} {self._serialize_data(self._update_data(data))}'

    def _get_logger_message(self, logger, last_version=False, **extra_data):
        if last_version:
            version = self.MAX_ELASTICSEARCH_VERSION
        elif 'last_elasticsearch_version' in logger.backend_logs:
            version = logger.backend_logs.last_elasticsearch_version + 1
        else:
            version = 0

        logger_data = self._update_data({
            **dict(
                slug=logger.slug,
                release=logger.release,
                related_objects=self._get_related_object_keys(logger),
                extra_data=logger.extra_data,
                parent_log=logger.parent_key,
            ),
            **logger.data,
            **extra_data
        })

        logger.backend_logs.last_elasticsearch_version = version
        return self._get_log_message(
            logger.id,
            logger.name,
            version,
            logger_data
        )

    def create_or_update_index_from_logger(self, logger, is_last=False, **extra_data):
        logstash_logger.info(
            self._get_logger_message(
                logger,
                last_version=is_last,
                **extra_data
            )
        )

    def update_index(self, index, **updated_data):
        data = self._get_index_data(index)
        data.update(updated_data)
        logger_name = {v: k for k, v in logger_name_to_log_model.items()}[index.__class__]
        logstash_logger.info(
            self._get_log_message(
                index.id,
                logger_name,
                self.MAX_ELASTICSEARCH_VERSION,
                self._update_data(data)
            )
        )


class ElasticsearchBackendWriter(BaseBackendWriter):

    def get_data_writer(self):
        return (
            LogstashElasticsearchDataWriter()
            if settings.ELASTICSEARCH_LOGSTASH_WRITER else DirectElasticsearchDataWriter()
        )

    def input_request_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(logger, state=RequestLogState.INCOMPLETE)

    def input_request_finished(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=get_response_state(logger.data['response_code'])
        )

    def input_request_error(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(logger, state=RequestLogState.ERROR)

    def output_request_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(logger, state=RequestLogState.INCOMPLETE)

    def output_request_finished(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=get_response_state(logger.data['response_code'])
        )

    def output_request_error(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=RequestLogState.ERROR
        )

    def command_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CommandState.ACTIVE
        )

    def command_output_updated(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CommandState.ACTIVE
        )

    def command_finished(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CommandState.SUCCEEDED
        )

    def command_error(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CommandState.FAILED
        )

    def celery_task_invocation_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CeleryTaskInvocationLogState.WAITING
        )

    def celery_task_invocation_triggered(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CeleryTaskInvocationLogState.TRIGGERED
        )

    def celery_task_invocation_ignored(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.IGNORED
        )

    def celery_task_invocation_timeout(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.TIMEOUT
        )

    def celery_task_invocation_expired(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.EXPIRED
        )

        if logger.data['celery_task_id']:
            celery_task_run_log_qs = CeleryTaskRunLog.search().filter(
                Q('term', celery_task_id=logger.data['celery_task_id'])
                & Q('term', state=CeleryTaskRunLogState.ACTIVE.name)
            )
            for celery_task_run in celery_task_run_log_qs:
                self.get_data_writer().update_index(
                    celery_task_run, state=CeleryTaskRunLogState.EXPIRED, stop=logger.data['stop']
                )

    def celery_task_run_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CeleryTaskRunLogState.ACTIVE
        )

    def celery_task_run_succeeded(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskRunLogState.SUCCEEDED
        )

        CeleryTaskInvocationLog._index.refresh()
        celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
            'term', celery_task_id=logger.data['celery_task_id']
        ).query(
            Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
            | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
            | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
        )
        for celery_task_invocation in celery_task_invocations_qs:
            self.get_data_writer().update_index(
                celery_task_invocation,
                state=CeleryTaskInvocationLogState.SUCCEEDED,
                stop=logger.data['stop'],
            )

    def celery_task_run_failed(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskRunLogState.FAILED
        )
        CeleryTaskInvocationLog._index.refresh()
        celery_task_invocations_qs = CeleryTaskInvocationLog.search().filter(
            'term', celery_task_id=logger.data['celery_task_id']
        ).query(
            Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
            | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
            | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
        )
        for celery_task_invocation in celery_task_invocations_qs:
            self.get_data_writer().update_index(
                celery_task_invocation,
                state=CeleryTaskInvocationLogState.FAILED,
                stop=logger.data['stop'],
            )

    def celery_task_run_retried(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskRunLogState.RETRIED
        )

    def celery_task_run_output_updated(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CeleryTaskRunLogState.ACTIVE
        )

    def set_stale_celery_task_log_state(self):
        processsing_stale_tasks = CeleryTaskInvocationLog.search().filter(
            Q('range', stale_at={'lt': now()}) & Q(
                Q('term', state=CeleryTaskInvocationLogState.WAITING.name)
                | Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
                | Q('term', state=CeleryTaskInvocationLogState.ACTIVE.name)
            )
        ).sort('stale_at')
        for task in processsing_stale_tasks[:settings.SET_STALE_CELERY_INVOCATIONS_LIMIT_PER_RUN]:
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                self.get_data_writer().update_index(
                    task, state=CeleryTaskInvocationLogState.SUCCEEDED, stop=task_last_run.stop
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                self.get_data_writer().update_index(
                    task, state=CeleryTaskInvocationLogState.FAILED, stop=task_last_run.stop
                )
            else:
                try:
                    task_args = json.loads(task.task_args),
                    task_kwargs = json.loads(task.task_kwargs),
                    current_app.tasks[task.name].expire_invocation(
                        task.id,
                        task_args,
                        task_kwargs,
                        dict(
                            slug=task.slug,
                            parent_key=task.parent_log,
                            related_objects=[
                                get_object_triple_from_key(key) for key in task.related_objects or ()
                            ],
                            data=dict(
                                start=task.start,
                                celery_task_id=task.celery_task_id,
                                stop=now(),
                                name=task.name,
                                queue_name=task.queue_name,
                                applied_at=task.applied_at,
                                triggered_at=task.triggered_at,
                                is_unique=task.is_unique,
                                is_async=task.is_async,
                                is_duplicate=task.is_duplicate,
                                is_on_commit=task.is_on_commit,
                                input=task.input,
                                task_args=task_args,
                                task_kwargs=task_kwargs,
                                estimated_time_of_first_arrival=task.estimated_time_of_first_arrival,
                                expires_at=task.expires_at,
                                stale_at=task.stale_at,
                            )
                        )
                    )
                except NotRegistered:
                    self.get_data_writer().update_index(
                        task, state=CeleryTaskInvocationLogState.EXPIRED, stop=task_last_run.stop
                    )

    def clean_logs(self, type, timestamp, backup_path, stdout):
        storage = import_string(settings.BACKUP_STORAGE_CLASS)()

        qs = get_log_model_from_logger_name(type).search().filter(Q('range', stop={'lt': timestamp})).sort('stop')
        step_timestamp = None
        if qs.count() != 0:
            step_timestamp = list(qs[0:1])[0].stop

        while step_timestamp and step_timestamp < timestamp:
            min_timestamp = datetime.combine(step_timestamp, time.min).replace(tzinfo=utc)
            max_timestamp = datetime.combine(step_timestamp, time.max).replace(tzinfo=utc)

            qs_filtered_by_day = qs.filter(Q('range', stop={'gte': min_timestamp, 'lte': max_timestamp}))

            if qs_filtered_by_day.count() != 0:
                stdout.write(
                    2 * ' ' + 'Cleaning logs for date {} ({})'.format(
                        step_timestamp.date(), qs_filtered_by_day.count()
                    )
                )

                if backup_path:
                    for qs_batch in get_querysets_by_batch(qs_filtered_by_day, settings.PURGE_LOG_BACKUP_BATCH):
                        log_file_name = os.path.join(backup_path, str(step_timestamp.date()))
                        if storage.exists('{}.json.gz'.format(log_file_name)):
                            i = 1
                            while storage.exists('{}({}).json.gz'.format(log_file_name, i)):
                                i += 1
                            log_file_name = '{}({})'.format(log_file_name, i)
                        stdout.write(4 * ' ' + 'generating backup file: {}.json.gz'.format(log_file_name))
                        with storage.open('{}.json.gz'.format(log_file_name), 'wb') as f:
                            with TextIOWrapper(gzip.GzipFile(filename='{}.json'.format(log_file_name),
                                                             fileobj=f, mode='wb')) as gzf:
                                json.dump(
                                    lazy_serialize_qs_without_pk(qs_batch), gzf, cls=DjangoJSONEncoder, indent=5
                                )
                stdout.write(4 * ' ' + 'deleting logs')
                qs_filtered_by_day.delete()

            step_timestamp = min_timestamp + timedelta(days=1)
