import os
import json
import gzip
import logging
import time as time_sleep

from itertools import islice, chain

from enum import Enum

from io import TextIOWrapper

from datetime import datetime, time, timedelta

from elasticsearch_dsl.utils import AttrDict, AttrList

from django.utils.timezone import now, utc
from django.utils.module_loading import import_string
from django.core.serializers.json import DjangoJSONEncoder

from celery import current_app
from celery.exceptions import NotRegistered

from elasticsearch import ConflictError, ConnectionTimeout
from elasticsearch_dsl import Q

from security.config import settings
from security.enums import (
    RequestLogState, CeleryTaskInvocationLogState, CeleryTaskRunLogState, CommandState
)
from security.backends.writer import BaseBackendWriter

from .models import (
    CeleryTaskInvocationLog, get_key_from_content_type_object_id_and_model_db, get_response_state,
    get_log_model_from_logger_name, get_object_triple_from_key, logger_name_to_log_model, get_index_name
)


logstash_logger = logging.getLogger('security.logstash')

MAX_VERSION = 9999


def batch_delete_queryset(queryset, batch, stdout, stderr, attempt=0):
    try:
        tmp_params = queryset._params.copy()
        queryset._params['max_docs'] = batch
        queryset._params['refresh'] = True
        queryset._params['request_timeout'] = settings.ELASTICSEARCH_CLEAN_LOGS_DELETE_REQUEST_TIMEOUT
        while True:
            stdout.write('.', ending='')
            if queryset.delete()['deleted'] == 0:
                break
        queryset._params = tmp_params
    except (ConflictError, ConnectionTimeout):
        if attempt > settings.ELASTICSEARCH_CLEAN_LOGS_DELETE_ATTEMPTS:
            raise
        time_sleep.sleep(settings.ELASTICSEARCH_CLEAN_LOGS_DELETE_ATTEMPT_SLEEP)
        stderr.write('.', ending='')
        queryset._params = tmp_params
        batch_delete_queryset(queryset, batch, stdout, stderr, attempt+1)


def batch(iterable, size):
    sourceiter = iter(iterable)
    try:
        while True:
            batchiter = islice(sourceiter, size)
            yield chain([next(batchiter)], batchiter)
    except StopIteration:
        pass


def get_queryset_dict_data_by_batch(qs, batch_size):
    for batch_qs in get_querysets_by_batch(qs, batch_size):
        for obj in batch_qs:
            yield obj.to_dict()


def get_lazy_serialize_iterable(iterable, stdout, batch):

    class StreamList(list):

        def __iter__(self):
            for i, obj in enumerate(iterable, 1):
                if i % batch == 0:
                    stdout.write('.', ending='')
                yield obj

        def __len__(self):
            return 1

    return StreamList()


def get_querysets_by_batch(qs, batch):
    last_document = None
    while True:
        batch_qs = qs
        if last_document:
            batch_qs = batch_qs.extra(search_after=last_document.meta.sort)

        batch_list = list(batch_qs[:batch])
        yield batch_list

        if len(batch_list) == batch:
            last_document = batch_list[-1]
        else:
            break


class BaseElasticsearchDataWriter:

    def _get_related_object_keys(self, logger):
        return [
            get_key_from_content_type_object_id_and_model_db(content_type_pk, object_pk, model_db)
            for model_db, content_type_pk, object_pk in logger.related_objects
        ]

    def _get_index_data(self, index):
        index_data = {}
        for field_name in index._doc_type.mapping.properties.to_dict()['properties'].keys():
            value = getattr(index, field_name)
            if isinstance(value, AttrList):
                value = value._l_
            elif isinstance(value, AttrDict):
                value = value.to_dict()

            index_data[field_name] = value
        return index_data

    def update_index(self, index, **updated_data):
        raise NotImplementedError

    def create_or_update_index_from_logger(self, logger, is_last=False, **extra_data):
        raise NotImplementedError


class DirectElasticsearchDataWriter(BaseElasticsearchDataWriter):

    def _create_index(self, logger_id, logger_name, version, data):
        try:
            index_class = get_log_model_from_logger_name(logger_name)
            index = index_class(**data)
            index.meta.id = logger_id
            index.save(
                params={
                    'version': version,
                    'version_type': 'external'
                }
            )
        except ConflictError:
            pass

    def update_index(self, index, **updated_data):
        data = self._get_index_data(index)
        data.update(updated_data)
        logger_name = {v: k for k, v in logger_name_to_log_model.items()}[index.__class__]
        self._create_index(
            index.id,
            logger_name,
            MAX_VERSION,
            data
        )

    def create_or_update_index_from_logger(self, logger, is_last=False, **extra_data):
        if is_last:
            version = MAX_VERSION
        elif 'last_elasticsearch_version' in logger.backend_logs:
            version = logger.backend_logs.last_elasticsearch_version + 1
        else:
            version = 0

        data = logger.to_dict()

        data['related_objects'] = self._get_related_object_keys(logger)
        data.update(extra_data)

        self._create_index(
            logger.id,
            logger.logger_name,
            version,
            data
        )
        logger.backend_logs.last_elasticsearch_version = version


class LogstashElasticsearchDataWriter(BaseElasticsearchDataWriter):

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
        return f'{get_index_name(logger_name)} {version} {logger_id} {self._serialize_data(data)}'

    def _get_logger_message(self, logger, last_version=False, **extra_data):
        if last_version:
            version = MAX_VERSION
        elif 'last_elasticsearch_version' in logger.backend_logs:
            version = logger.backend_logs.last_elasticsearch_version + 1
        else:
            version = 0

        logger_data = logger.to_dict()
        logger_data['related_objects'] = self._get_related_object_keys(logger)
        logger_data.update(extra_data)

        logger.backend_logs.last_elasticsearch_version = version
        return self._get_log_message(
            logger.id,
            logger.logger_name,
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
                MAX_VERSION,
                data
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
            logger, is_last=True, state=get_response_state(logger.response_code)
        )

    def input_request_error(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(logger, state=RequestLogState.ERROR)

    def output_request_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(logger, state=RequestLogState.INCOMPLETE)

    def output_request_finished(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=get_response_state(logger.response_code)
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

    def celery_task_invocation_duplicate(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.DUPLICATE
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

    def celery_task_invocation_succeeded(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.SUCCEEDED
        )

    def celery_task_invocation_failed(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskInvocationLogState.FAILED
        )

    def celery_task_run_started(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, state=CeleryTaskRunLogState.ACTIVE
        )

    def celery_task_run_succeeded(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskRunLogState.SUCCEEDED
        )

    def celery_task_run_failed(self, logger):
        self.get_data_writer().create_or_update_index_from_logger(
            logger, is_last=True, state=CeleryTaskRunLogState.FAILED
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
            Q('range', stale_at={'lt': now()}) & Q('term', state=CeleryTaskInvocationLogState.TRIGGERED.name)
        ).sort('stale_at')
        for task in processsing_stale_tasks[:settings.SET_STALE_CELERY_INVOCATIONS_LIMIT_PER_RUN]:
            task_last_run = task.last_run
            if task_last_run and task_last_run.state == CeleryTaskRunLogState.SUCCEEDED:
                self.get_data_writer().update_index(
                    task,
                    state=CeleryTaskInvocationLogState.SUCCEEDED,
                    stop=task_last_run.stop,
                    time=(task_last_run.stop - task.start).total_seconds()
                )
            elif task_last_run and task_last_run.state == CeleryTaskRunLogState.FAILED:
                self.get_data_writer().update_index(
                    task,
                    state=CeleryTaskInvocationLogState.FAILED,
                    stop=task_last_run.stop,
                    time=(task_last_run.stop - task.start).total_seconds()
                )
            else:
                try:
                    task_args = json.loads(task.task_args)
                    task_kwargs = json.loads(task.task_kwargs)
                    current_app.tasks[task.name].expire_invocation(
                        task.id,
                        task_args,
                        task_kwargs,
                        dict(
                            slug=task.slug,
                            parent_log=task.parent_log,
                            related_objects=[
                                get_object_triple_from_key(key) for key in task.related_objects or ()
                            ],
                            start=task.start,
                            celery_task_id=task.celery_task_id,
                            stop=task.stop,
                            name=task.name,
                            queue_name=task.queue_name,
                            applied_at=task.applied_at,
                            triggered_at=task.triggered_at,
                            is_unique=task.is_unique,
                            is_async=task.is_async,
                            is_on_commit=task.is_on_commit,
                            input=task.input,
                            task_args=task_args,
                            task_kwargs=task_kwargs,
                            estimated_time_of_first_arrival=task.estimated_time_of_first_arrival,
                            expires_at=task.expires_at,
                            stale_at=task.stale_at,
                        )
                    )
                except NotRegistered:
                    self.get_data_writer().update_index(
                        task,
                        state=CeleryTaskInvocationLogState.EXPIRED,
                        stop=now()
                    )

    def clean_logs(self, type, timestamp, backup_path, stdout, stderr):
        storage = import_string(settings.BACKUP_STORAGE_CLASS)()

        qs = get_log_model_from_logger_name(type).search().filter(
            Q('range', start={'lt': timestamp})
        ).sort('start')
        step_timestamp = None
        if qs.count() != 0:
            step_timestamp = list(qs[0:1])[0].start

        while step_timestamp and step_timestamp < timestamp:
            min_timestamp = datetime.combine(step_timestamp, time.min).replace(tzinfo=utc)
            max_timestamp = datetime.combine(step_timestamp, time.max).replace(tzinfo=utc)

            qs_filtered_by_day = qs.filter(Q('range', start={'gte': min_timestamp, 'lte': max_timestamp})).sort(
                'start', 'id'
            )

            if qs_filtered_by_day.count() != 0:
                stdout.write(
                    2 * ' ' + 'Cleaning logs for date {} ({})'.format(
                        step_timestamp.date(), qs_filtered_by_day.count()
                    )
                )

                if backup_path:
                    created_log_files = []

                    try:
                        for batch_data in batch(
                                get_queryset_dict_data_by_batch(
                                    qs_filtered_by_day, settings.ELASTICSEARCH_CLEAN_LOGS_READ_BATCH_SIZE
                                ),
                                settings.CLEAN_LOGS_BACKUP_FILE_BATCH_SIZE):
                            log_file_name = os.path.join(backup_path, str(step_timestamp.date()))
                            if storage.exists(f'{log_file_name}.json.gz'):
                                i = 1
                                while storage.exists(f'{log_file_name}({i}).json.gz'):
                                    i += 1
                                log_file_name = f'{log_file_name}({i})'
                            log_file_name = f'{log_file_name}.json.gz'
                            stdout.write(4 * ' ' + f'generating backup file: {log_file_name}', ending=' ')
                            with storage.open(log_file_name, 'wb') as f:
                                with TextIOWrapper(gzip.GzipFile(filename='{}.json'.format(log_file_name),
                                                                 fileobj=f, mode='wb')) as gzf:
                                    created_log_files.append(log_file_name)
                                    json.dump(
                                        get_lazy_serialize_iterable(
                                            batch_data, stdout, settings.ELASTICSEARCH_CLEAN_LOGS_READ_BATCH_SIZE
                                        ),
                                        gzf, cls=DjangoJSONEncoder, indent=5
                                    )
                            stdout.write('')
                    except Exception:
                        stdout.write('')
                        stderr.write(4 * ' ' + 'raised exception removing created files')
                        for log_file_name in created_log_files:
                            storage.delete(log_file_name)
                        raise
                stdout.write(4 * ' ' + 'deleting logs', ending=' ')
                batch_delete_queryset(
                    qs_filtered_by_day, settings.ELASTICSEARCH_CLEAN_LOGS_DELETE_BATCH_SIZE, stdout, stderr
                )
                stdout.write('')

            step_timestamp = min_timestamp + timedelta(days=1)
