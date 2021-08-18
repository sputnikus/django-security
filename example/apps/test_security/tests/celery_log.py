from uuid import uuid4
from unittest import mock
import responses
from datetime import timedelta

from django import get_version
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.db import transaction
from django.test import override_settings
from django.utils.timezone import now

from freezegun import freeze_time

from celery.exceptions import TimeoutError

from germanium.decorators import data_consumer
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_equal, assert_false, assert_http_not_found, assert_http_ok, assert_http_redirect,
    assert_http_too_many_requests, assert_in, assert_is_none, assert_is_not_none, assert_not_in,
    assert_raises, assert_true, assert_equal_model_fields, capture_on_commit_callbacks
)

from chamber.utils.transaction import transaction_signals
from chamber.shortcuts import change_and_save

from django_celery_extensions.task import get_django_command_task

from security.config import settings
from security.decorators import log_with_data
from security.enums import CeleryTaskInvocationLogState, CeleryTaskRunLogState
from security.backends.sql.models import CeleryTaskRunLog as SQLCeleryTaskRunLog
from security.backends.sql.models import CeleryTaskInvocationLog as SQLCeleryTaskInvocationLog
from security.backends.elasticsearch.models import CeleryTaskRunLog as ElasticsearchCeleryTaskRunLog
from security.backends.elasticsearch.models import CeleryTaskInvocationLog as ElasticsearchCeleryTaskInvocationLog

from security.backends.signals import (
    celery_task_invocation_started, celery_task_invocation_expired, celery_task_invocation_triggered,
    celery_task_invocation_ignored, celery_task_invocation_timeout, celery_task_run_started, celery_task_run_failed,
    celery_task_run_retried, celery_task_run_succeeded, celery_task_run_output_updated
)

from apps.test_security.tasks import error_task, retry_task, sum_task, unique_task, ignored_after_success_task

from .base import (
    BaseTestCaseMixin, _all_, TRUNCATION_CHAR, assert_equal_dict_data, set_signal_receiver, test_call_command,
    _not_none_
)


@override_settings(SECURITY_BACKENDS={})
class CeleryLogTestCase(BaseTestCaseMixin, ClientTestCase):

    @data_consumer('create_user')
    def test_sum_celery_task_should_be_logged(self, user):
        expected_invocation_started_data = {
            'name': 'sum_task',
            'queue_name': 'default',
            'input': '5, 8',
            'task_args': [5, 8],
            'task_kwargs': {},
            'applied_at': _not_none_,
            'is_async': False,
            'is_unique': False,
            'is_on_commit': False,
            'start': _not_none_,
        }
        expected_invocation_triggered_data = {
            **expected_invocation_started_data,
            'triggered_at': _not_none_,
            'stale_at': None,
            'estimated_time_of_first_arrival': _not_none_,
            'expires_at': None,
            'celery_task_id': _not_none_,
            'is_duplicate': False,
        }

        expected_run_started_data = {
            'name': 'sum_task',
            'queue_name': None,
            'input': '5, 8',
            'task_args': [5, 8],
            'task_kwargs': {},
            'start': _not_none_,
            'retries': 0,
            'celery_task_id': _not_none_,
        }
        expected_run_succeeded_data = {
            **expected_run_started_data,
            'stop': _not_none_,
            'result': 13
        }

        with set_signal_receiver(celery_task_invocation_started,
                                 expected_invocation_started_data) as invocation_started_receiver, \
                set_signal_receiver(celery_task_invocation_triggered,
                                    expected_invocation_triggered_data) as invocation_triggered_receiver, \
                set_signal_receiver(celery_task_run_started,
                                    expected_run_started_data) as run_started_receiver, \
                set_signal_receiver(celery_task_run_succeeded,
                                    expected_run_succeeded_data) as run_succeeded_receiver, \
                set_signal_receiver(celery_task_run_output_updated) as run_output_updated_receiver, \
                set_signal_receiver(celery_task_run_failed) as run_failed_receiver, \
                set_signal_receiver(celery_task_run_retried) as run_retried_receiver:
            sum_task.apply(args=(5, 8), related_objects=[user])
            assert_equal(invocation_started_receiver.calls, 1)
            assert_equal(invocation_triggered_receiver.calls, 1)
            assert_equal(run_started_receiver.calls, 1)
            assert_equal(run_succeeded_receiver.calls, 1)
            assert_equal(run_output_updated_receiver.calls, 1)
            assert_equal(run_failed_receiver.calls, 0)
            assert_equal(run_retried_receiver.calls, 0)
            assert_equal(invocation_started_receiver.last_logger.related_objects, {user})

    def test_error_celery_task_should_be_logged(self):
        expected_invocation_started_data = {
            'name': 'error_task',
            'queue_name': 'default',
            'input': '',
            'task_args': [],
            'task_kwargs': {},
            'applied_at': _not_none_,
            'is_async': False,
            'is_unique': False,
            'is_on_commit': False,
            'start': _not_none_,
        }
        expected_invocation_triggered_data = {
            **expected_invocation_started_data,
            'triggered_at': _not_none_,
            'stale_at': _not_none_,
            'estimated_time_of_first_arrival': _not_none_,
            'expires_at': None,
            'celery_task_id': _not_none_,
            'is_duplicate': False,
        }

        expected_run_started_data = {
            'name': 'error_task',
            'queue_name': None,
            'input': '',
            'task_args': [],
            'task_kwargs': {},
            'start': _not_none_,
            'retries': 0,
            'celery_task_id': _not_none_,
        }
        expected_run_failed_data = {
            **expected_run_started_data,
            'stop': _not_none_,
            'error_message': _not_none_,
        }

        with set_signal_receiver(celery_task_invocation_started,
                                 expected_invocation_started_data) as invocation_started_receiver, \
                set_signal_receiver(celery_task_invocation_triggered,
                                    expected_invocation_triggered_data) as invocation_triggered_receiver, \
                set_signal_receiver(celery_task_run_started,
                                    expected_run_started_data) as run_started_receiver, \
                set_signal_receiver(celery_task_run_succeeded) as run_succeeded_receiver, \
                set_signal_receiver(celery_task_run_output_updated) as run_output_updated_receiver, \
                set_signal_receiver(celery_task_run_failed, expected_run_failed_data) as run_failed_receiver, \
                set_signal_receiver(celery_task_run_retried) as run_retried_receiver:
            error_task.apply()
            assert_equal(invocation_started_receiver.calls, 1)
            assert_equal(invocation_triggered_receiver.calls, 1)
            assert_equal(run_started_receiver.calls, 1)
            assert_equal(run_succeeded_receiver.calls, 0)
            assert_equal(run_output_updated_receiver.calls, 1)
            assert_equal(run_failed_receiver.calls, 1)
            assert_equal(run_retried_receiver.calls, 0)

    def test_retry_celery_task_should_be_logged(self):
        expected_invocation_started_data = {
            'name': 'retry_task',
            'queue_name': 'default',
            'input': '',
            'task_args': [],
            'task_kwargs': {},
            'applied_at': _not_none_,
            'is_async': False,
            'is_unique': False,
            'is_on_commit': False,
            'start': _not_none_,
        }
        expected_invocation_triggered_data = {
            **expected_invocation_started_data,
            'triggered_at': _not_none_,
            'stale_at': None,
            'estimated_time_of_first_arrival': _not_none_,
            'expires_at': None,
            'celery_task_id': _not_none_,
            'is_duplicate': False,
        }

        expected_run_started_data = {
            'name': 'retry_task',
            'queue_name': None,
            'input': '',
            'task_args': [],
            'task_kwargs': {},
            'start': _not_none_,
            'retries': _not_none_,
            'celery_task_id': _not_none_,
        }
        expected_run_retried_data = {
            **expected_run_started_data,
            'stop': _not_none_,
            'error_message': _not_none_,
            'estimated_time_of_next_retry': _not_none_,
        }

        with set_signal_receiver(celery_task_invocation_started,
                                 expected_invocation_started_data) as invocation_started_receiver, \
                set_signal_receiver(celery_task_invocation_triggered,
                                    expected_invocation_triggered_data) as invocation_triggered_receiver, \
                set_signal_receiver(celery_task_run_started,
                                    expected_run_started_data) as run_started_receiver, \
                set_signal_receiver(celery_task_run_succeeded) as run_succeeded_receiver, \
                set_signal_receiver(celery_task_run_output_updated) as run_output_updated_receiver, \
                set_signal_receiver(celery_task_run_failed) as run_failed_receiver, \
                set_signal_receiver(celery_task_run_retried, expected_run_retried_data) as run_retried_receiver:
            retry_task.apply()
            assert_equal(invocation_started_receiver.calls, 1)
            assert_equal(invocation_triggered_receiver.calls, 1)
            assert_equal(run_started_receiver.calls, 6)
            assert_equal(run_succeeded_receiver.calls, 1)
            assert_equal(run_output_updated_receiver.calls, 6)
            assert_equal(run_failed_receiver.calls, 0)
            assert_equal(run_retried_receiver.calls, 5)

    @override_settings(DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=30, SECURITY_TASK_USE_ON_SUCCESS=True)
    def test_ignored_after_success_celery_task_should_be_logged(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_invocation_triggered) as invocation_triggered_receiver, \
                set_signal_receiver(celery_task_invocation_ignored) as invocation_ignored_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            with capture_on_commit_callbacks(execute=True):
                ignored_after_success_task.apply_async_on_commit()
                ignored_after_success_task.apply_async_on_commit()

            assert_equal(invocation_started_receiver.calls, 2)
            assert_equal(invocation_triggered_receiver.calls, 1)
            assert_equal(invocation_ignored_receiver.calls, 1)
            assert_equal(run_started_receiver.calls, 1)

    @override_settings(DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=5)
    def test_apply_async_and_get_result_should_return_time_error_for_zero_timeout(self):
        with set_signal_receiver(celery_task_invocation_timeout) as invocation_timeout_receiver:
            with assert_raises(TimeoutError):
                unique_task.apply_async_and_get_result(timeout=0)
            assert_equal(invocation_timeout_receiver.calls, 1)

    @override_settings(SECURITY_TASK_USE_ON_SUCCESS=True)
    def test_task_should_be_logged_with_on_commit_signal(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_invocation_triggered) as invocation_triggered_receiver:
            with capture_on_commit_callbacks(execute=True):
                with transaction_signals():
                    sum_task.apply_async_on_commit(args=(5, 8))
                    assert_equal(invocation_started_receiver.calls, 0)
                    assert_equal(invocation_triggered_receiver.calls, 0)
                assert_equal(invocation_started_receiver.calls, 1)
                assert_equal(invocation_triggered_receiver.calls, 0)
            assert_equal(invocation_started_receiver.calls, 1)
            assert_equal(invocation_triggered_receiver.calls, 1)

    @override_settings(SECURITY_TASK_USE_ON_SUCCESS=True)
    def test_unique_task_should_be_logged_as_duplicate_and_run_is_not_started(self):
        with mock.patch.object(unique_task, '_get_unique_task_id') as apply_method:
            unique_task_id = uuid4()
            apply_method.return_value = unique_task_id
            with set_signal_receiver(celery_task_invocation_triggered) as invocation_triggered_receiver, \
                    set_signal_receiver(celery_task_run_started) as run_started_receiver:
                unique_task.apply_async()
                assert_equal(invocation_triggered_receiver.calls, 1)
                assert_equal(run_started_receiver.calls, 0)
                assert_true(invocation_triggered_receiver.last_logger.data['is_duplicate'])
                assert_equal(invocation_triggered_receiver.last_logger.data['celery_task_id'], unique_task_id)

    def test_data_change_should_be_connected_with_celery_task_run_log(self):
        with set_signal_receiver(celery_task_run_started) as run_started_receiver:
            get_django_command_task('create_user').apply_async()
            assert_equal(
                list(run_started_receiver.last_logger.related_objects)[0].version_set.get().content_type,
                ContentType.objects.get_for_model(User)
            )

    @override_settings(SECURITY_BACKENDS={'sql'})
    @data_consumer('create_user')
    def test_sum_celery_task_should_be_logged_in_sql_backend(self, user):
        with log_with_data(related_objects=[user]):
            sum_task.apply(args=(5, 8), related_objects=[user])
            assert_equal(SQLCeleryTaskInvocationLog.objects.count(), 1)
            assert_equal(SQLCeleryTaskRunLog.objects.count(), 1)
            sql_celery_task_invocation_log = SQLCeleryTaskInvocationLog.objects.get()
            sql_celery_task_run_log = SQLCeleryTaskRunLog.objects.get()

            assert_equal_model_fields(
                sql_celery_task_invocation_log,
                state=CeleryTaskInvocationLogState.SUCCEEDED,
                name='sum_task',
                time=(sql_celery_task_invocation_log.stop - sql_celery_task_invocation_log.start).total_seconds(),
                stale_at=None,
                expires_at=None,
                is_duplicate=False,
                input='5, 8',
                task_args=[5, 8],
                task_kwargs={},
                queue_name='default'
            )
            assert_is_not_none(sql_celery_task_invocation_log.celery_task_id)
            assert_equal([rel_obj.object for rel_obj in sql_celery_task_invocation_log.related_objects.all()], [user])
            assert_equal_model_fields(
                sql_celery_task_run_log,
                state=CeleryTaskRunLogState.SUCCEEDED,
                name='sum_task',
                time=(sql_celery_task_run_log.stop - sql_celery_task_run_log.start).total_seconds(),
                input='5, 8',
                task_args=[5, 8],
                task_kwargs={},
                queue_name=None,
                retries=0
            )

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @data_consumer('create_user')
    def test_sum_celery_task_should_be_logged_in_elasticsearch_backend(self, user):
        with log_with_data(related_objects=[user]):
            with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                    set_signal_receiver(celery_task_run_started) as run_started_receiver:
                sum_task.apply(args=(5, 8), related_objects=[user])

                elasticsearch_celery_task_invocation_log = ElasticsearchCeleryTaskInvocationLog.get(
                    id=invocation_started_receiver.last_logger.id
                )
                elasticsearch_celery_task_run_log = ElasticsearchCeleryTaskRunLog.get(
                    id=run_started_receiver.last_logger.id
                )

                assert_equal_model_fields(
                    elasticsearch_celery_task_invocation_log,
                    state=CeleryTaskInvocationLogState.SUCCEEDED,
                    name='sum_task',
                    time=(
                        elasticsearch_celery_task_invocation_log.stop - elasticsearch_celery_task_invocation_log.start
                    ).total_seconds(),
                    stale_at=None,
                    expires_at=None,
                    is_duplicate=False,
                    input='5, 8',
                    task_args='[5, 8]',
                    task_kwargs='{}',
                    queue_name='default'
                )
                assert_is_not_none(elasticsearch_celery_task_invocation_log.celery_task_id)
                assert_equal(
                    [rel_obj for rel_obj in elasticsearch_celery_task_invocation_log.related_objects],
                    ['default|3|{}'.format(user.id)]
                )
                assert_equal_model_fields(
                    elasticsearch_celery_task_run_log,
                    state=CeleryTaskRunLogState.SUCCEEDED,
                    name='sum_task',
                    time=(
                        elasticsearch_celery_task_run_log.stop - elasticsearch_celery_task_run_log.start
                    ).total_seconds(),
                    input='5, 8',
                    task_args='[5, 8]',
                    task_kwargs='{}',
                    queue_name=None,
                    retries=0
                )

    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_sum_celery_task_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            with self.assertLogs('security.celery', level='INFO') as cm:
                sum_task.apply(args=(5, 8))

                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.celery:'
                        f'Celery task invocation "{invocation_started_receiver.last_logger.id}" '
                        f'with celery id "{invocation_started_receiver.last_logger.data["celery_task_id"]}" '
                        f'and name "sum_task" is triggered',
                        f'INFO:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                        f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "sum_task" is '
                        f'started',
                        f'INFO:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                        f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "sum_task" is '
                        f'completed',
                    ]
                )

    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_error_celery_task_should_be_logged_in_sql_backend(self):
        error_task.apply()
        assert_equal(SQLCeleryTaskInvocationLog.objects.count(), 1)
        assert_equal(SQLCeleryTaskRunLog.objects.count(), 1)
        sql_celery_task_invocation_log = SQLCeleryTaskInvocationLog.objects.get()
        sql_celery_task_run_log = SQLCeleryTaskRunLog.objects.get()

        assert_equal_model_fields(
            sql_celery_task_invocation_log,
            state=CeleryTaskInvocationLogState.FAILED,
            name='error_task',
            time=(sql_celery_task_invocation_log.stop - sql_celery_task_invocation_log.start).total_seconds(),
            expires_at=None,
            is_duplicate=False,
            input='',
            task_args=[],
            task_kwargs={},
            queue_name='default'
        )
        assert_is_not_none(sql_celery_task_invocation_log.celery_task_id)
        assert_equal_model_fields(
            sql_celery_task_run_log,
            state=CeleryTaskRunLogState.FAILED,
            name='error_task',
            time=(sql_celery_task_run_log.stop - sql_celery_task_run_log.start).total_seconds(),
            input='',
            task_args=[],
            task_kwargs={},
            queue_name=None,
            retries=0
        )
        assert_is_not_none(sql_celery_task_run_log.error_message)

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    def test_error_celery_task_should_be_logged_in_elasticsearch_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            error_task.apply()
            elasticsearch_celery_task_invocation_log = ElasticsearchCeleryTaskInvocationLog.get(
                id=invocation_started_receiver.last_logger.id
            )
            elasticsearch_celery_task_run_log = ElasticsearchCeleryTaskRunLog.get(
                id=run_started_receiver.last_logger.id
            )

            assert_equal_model_fields(
                elasticsearch_celery_task_invocation_log,
                state=CeleryTaskInvocationLogState.FAILED,
                name='error_task',
                time=(
                    elasticsearch_celery_task_invocation_log.stop - elasticsearch_celery_task_invocation_log.start
                ).total_seconds(),
                expires_at=None,
                is_duplicate=False,
                input='',
                task_args='[]',
                task_kwargs='{}',
                queue_name='default'
            )
            assert_is_not_none(elasticsearch_celery_task_invocation_log.celery_task_id)
            assert_equal_model_fields(
                elasticsearch_celery_task_run_log,
                state=CeleryTaskRunLogState.FAILED,
                name='error_task',
                time=(elasticsearch_celery_task_run_log.stop - elasticsearch_celery_task_run_log.start).total_seconds(),
                input='',
                task_args='[]',
                task_kwargs='{}',
                queue_name=None,
                retries=0
            )
            assert_is_not_none(elasticsearch_celery_task_run_log.error_message)

    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_error_celery_task_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            with self.assertLogs('security.celery', level='INFO') as cm:
                error_task.apply()

                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.celery:'
                        f'Celery task invocation "{invocation_started_receiver.last_logger.id}" '
                        f'with celery id "{invocation_started_receiver.last_logger.data["celery_task_id"]}" '
                        f'and name "error_task" is triggered',
                        f'INFO:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                        f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "error_task" '
                        f'is started',
                        f'ERROR:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                        f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "error_task" '
                        f'is failed',
                    ]
                )

    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_retry_celery_task_should_be_logged_in_sql_backend(self):
        with set_signal_receiver(celery_task_run_started) as run_started_receiver:
            retry_task.apply()
            assert_equal(SQLCeleryTaskInvocationLog.objects.count(), 1)
            assert_equal(SQLCeleryTaskRunLog.objects.count(), 6)

            sql_celery_task_invocation_log = SQLCeleryTaskInvocationLog.objects.get()
            assert_equal_model_fields(
                sql_celery_task_invocation_log,
                state=CeleryTaskInvocationLogState.SUCCEEDED,
                name='retry_task',
                time=(sql_celery_task_invocation_log.stop - sql_celery_task_invocation_log.start).total_seconds(),
                expires_at=None,
                is_duplicate=False,
                input='',
                task_args=[],
                task_kwargs={},
                queue_name='default'
            )

            for i, logger in enumerate(run_started_receiver.loggers[0:5]):
                sql_celery_task_run_log = SQLCeleryTaskRunLog.objects.get(id=logger.id)
                assert_equal_model_fields(
                    sql_celery_task_run_log,
                    state=CeleryTaskRunLogState.RETRIED,
                    name='retry_task',
                    time=(sql_celery_task_run_log.stop - sql_celery_task_run_log.start).total_seconds(),
                    input='',
                    task_args=[],
                    task_kwargs={},
                    queue_name=None,
                    retries=i
                )
                assert_is_not_none(sql_celery_task_run_log.error_message)
            sql_celery_task_run_log = SQLCeleryTaskRunLog.objects.get(id=run_started_receiver.last_logger.id)
            assert_equal_model_fields(
                sql_celery_task_run_log,
                state=CeleryTaskRunLogState.SUCCEEDED,
                name='retry_task',
                time=(sql_celery_task_run_log.stop - sql_celery_task_run_log.start).total_seconds(),
                input='',
                task_args=[],
                task_kwargs={},
                queue_name=None,
                retries=5,
                error_message=None
            )
            assert_equal(sql_celery_task_invocation_log.last_run.id, sql_celery_task_run_log.id)

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    def test_retry_celery_task_should_be_logged_in_elasticsearch_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            retry_task.apply()

            elasticsearch_celery_task_invocation_log = ElasticsearchCeleryTaskInvocationLog.get(
                id=invocation_started_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_celery_task_invocation_log,
                state=CeleryTaskInvocationLogState.SUCCEEDED,
                name='retry_task',
                time=(
                    elasticsearch_celery_task_invocation_log.stop - elasticsearch_celery_task_invocation_log.start
                ).total_seconds(),
                expires_at=None,
                is_duplicate=False,
                input='',
                task_args='[]',
                task_kwargs='{}',
                queue_name='default'
            )

            for i, logger in enumerate(run_started_receiver.loggers[0:5]):
                elasticsearch_celery_task_run_log = ElasticsearchCeleryTaskRunLog.get(
                    id=logger.id
                )
                assert_equal_model_fields(
                    elasticsearch_celery_task_run_log,
                    state=CeleryTaskRunLogState.RETRIED,
                    name='retry_task',
                    time=(
                        elasticsearch_celery_task_run_log.stop - elasticsearch_celery_task_run_log.start
                    ).total_seconds(),
                    input='',
                    task_args='[]',
                    task_kwargs='{}',
                    queue_name=None,
                    retries=i
                )
                assert_is_not_none(elasticsearch_celery_task_run_log.error_message)
            elasticsearch_celery_task_run_log = ElasticsearchCeleryTaskRunLog.get(
                id=run_started_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_celery_task_run_log,
                state=CeleryTaskRunLogState.SUCCEEDED,
                name='retry_task',
                time=(elasticsearch_celery_task_run_log.stop - elasticsearch_celery_task_run_log.start).total_seconds(),
                input='',
                task_args='[]',
                task_kwargs='{}',
                queue_name=None,
                retries=5,
                error_message=None
            )
            ElasticsearchCeleryTaskRunLog._index.refresh()
            assert_equal(elasticsearch_celery_task_invocation_log.last_run.id, elasticsearch_celery_task_run_log.id)

    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_retry_celery_task_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver, \
                set_signal_receiver(celery_task_run_started) as run_started_receiver:
            with self.assertLogs('security.celery', level='INFO') as cm:
                retry_task.apply()
                expected_output = [
                    f'INFO:security.celery:'
                    f'Celery task invocation "{invocation_started_receiver.last_logger.id}" '
                    f'with celery id "{invocation_started_receiver.last_logger.data["celery_task_id"]}" '
                    f'and name "retry_task" is triggered',
                ]
                for logger in run_started_receiver.loggers[0:5]:
                    expected_output += [
                        f'INFO:security.celery:Celery task "{logger.id}" with '
                        f'celery id "{logger.data["celery_task_id"]}" and name "retry_task" '
                        f'is started',
                        f'WARNING:security.celery:Celery task "{logger.id}" with '
                        f'celery id "{logger.data["celery_task_id"]}" and name "retry_task" '
                        f'is retried',
                    ]
                expected_output += [
                    f'INFO:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                    f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "retry_task" '
                    f'is started',
                    f'INFO:security.celery:Celery task "{run_started_receiver.last_logger.id}" with '
                    f'celery id "{run_started_receiver.last_logger.data["celery_task_id"]}" and name "retry_task" is '
                    f'completed',
                ]
                assert_equal(cm.output, expected_output)

    @override_settings(SECURITY_BACKENDS={'sql'}, DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=30)
    def test_set_celery_task_log_state_should_set_task_to_failed_with_sql_backend(self):
        with mock.patch.object(unique_task, '_get_unique_task_id') as apply_method:
            unique_task_id = uuid4()
            apply_method.return_value = unique_task_id
            unique_task.apply_async()

            sql_celery_task_invocation_log = SQLCeleryTaskInvocationLog.objects.get()
            test_call_command('sql_set_celery_task_log_state')
            sql_celery_task_invocation_log.refresh_from_db()
            assert_equal(
                sql_celery_task_invocation_log.state, CeleryTaskInvocationLogState.TRIGGERED
            )

            with freeze_time(now() + timedelta(seconds=30)):
                test_call_command('sql_set_celery_task_log_state')
                sql_celery_task_invocation_log.refresh_from_db()
                assert_equal(sql_celery_task_invocation_log.state, CeleryTaskInvocationLogState.EXPIRED)

    @override_settings(SECURITY_BACKENDS={'elasticsearch'}, DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=30)
    def test_set_celery_task_log_state_should_set_task_to_failed_with_elasticsearch_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver:
            with mock.patch.object(unique_task, '_get_unique_task_id') as apply_method:
                unique_task_id = uuid4()
                apply_method.return_value = unique_task_id
                unique_task.apply_async()
                ElasticsearchCeleryTaskInvocationLog._index.refresh()

                test_call_command('elasticsearch_set_celery_task_log_state')
                assert_equal(
                    ElasticsearchCeleryTaskInvocationLog.get(
                        id=invocation_started_receiver.last_logger.id
                    ).state, CeleryTaskInvocationLogState.TRIGGERED
                )

                with freeze_time(now() + timedelta(seconds=30)):
                    test_call_command('elasticsearch_set_celery_task_log_state')
                    assert_equal(
                        ElasticsearchCeleryTaskInvocationLog.get(
                            id=invocation_started_receiver.last_logger.id
                        ).state,
                        CeleryTaskInvocationLogState.EXPIRED
                    )

    @override_settings(SECURITY_BACKENDS={'sql'}, DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=30)
    def test_set_celery_task_log_state_should_set_task_to_succeeded_with_sql_backend(self):
        unique_task.apply_async()

        sql_celery_task_invocation_log = SQLCeleryTaskInvocationLog.objects.get()
        change_and_save(sql_celery_task_invocation_log, state=CeleryTaskInvocationLogState.TRIGGERED)

        test_call_command('sql_set_celery_task_log_state')
        sql_celery_task_invocation_log.refresh_from_db()
        assert_equal(
            sql_celery_task_invocation_log.state, CeleryTaskInvocationLogState.TRIGGERED
        )

        with freeze_time(now() + timedelta(seconds=30)):
            test_call_command('sql_set_celery_task_log_state')
            sql_celery_task_invocation_log.refresh_from_db()
            assert_equal(sql_celery_task_invocation_log.state, CeleryTaskInvocationLogState.SUCCEEDED)

    @override_settings(SECURITY_BACKENDS={'elasticsearch'}, DJANGO_CELERY_EXTENSIONS_DEFAULT_TASK_STALE_TIME_LIMIT=30)
    def test_set_celery_task_log_state_should_set_task_to_succeeded_with_elasticsearch_backend(self):
        with set_signal_receiver(celery_task_invocation_started) as invocation_started_receiver:
            unique_task.apply_async()
            ElasticsearchCeleryTaskInvocationLog.get(
                id=invocation_started_receiver.last_logger.id
            ).update(state=CeleryTaskInvocationLogState.TRIGGERED)
            ElasticsearchCeleryTaskInvocationLog._index.refresh()
            ElasticsearchCeleryTaskRunLog._index.refresh()

            test_call_command('elasticsearch_set_celery_task_log_state')
            assert_equal(
                ElasticsearchCeleryTaskInvocationLog.get(
                    id=invocation_started_receiver.last_logger.id
                ).state, CeleryTaskInvocationLogState.TRIGGERED
            )

            with freeze_time(now() + timedelta(seconds=30)):
                test_call_command('elasticsearch_set_celery_task_log_state')
                assert_equal(
                    ElasticsearchCeleryTaskInvocationLog.get(
                        id=invocation_started_receiver.last_logger.id
                    ).state,
                    CeleryTaskInvocationLogState.SUCCEEDED
                )
