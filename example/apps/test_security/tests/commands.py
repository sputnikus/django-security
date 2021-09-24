import responses
from datetime import timedelta

from freezegun import freeze_time

from django.test import override_settings
from django.utils.timezone import now

from germanium.decorators import data_consumer
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_equal, assert_false, assert_http_not_found, assert_http_ok, assert_http_redirect,
    assert_http_too_many_requests, assert_in, assert_is_none, assert_is_not_none, assert_not_in,
    assert_raises, assert_true, assert_equal_model_fields
)

from security import requests
from security.backends.sql.models import CommandLog as SQLCommandLog
from security.backends.elasticsearch.models import CommandLog as ElasticsearchCommandLog
from security.backends.sql.models import CeleryTaskRunLog as SQLCeleryTaskRunLog
from security.backends.sql.models import CeleryTaskInvocationLog as SQLCeleryTaskInvocationLog
from security.backends.elasticsearch.models import CeleryTaskRunLog as ElasticsearchCeleryTaskRunLog
from security.backends.elasticsearch.models import CeleryTaskInvocationLog as ElasticsearchCeleryTaskInvocationLog
from security.backends.sql.models import InputRequestLog as SQLInputRequestLog
from security.backends.elasticsearch.models import InputRequestLog as ElasticsearchInputRequestLog
from security.backends.sql.models import OutputRequestLog as SQLOutputRequestLog
from security.backends.elasticsearch.models import OutputRequestLog as ElasticsearchOutputRequestLog

from security.backends.signals import (
    command_started, input_request_started, output_request_started, celery_task_invocation_started,
    celery_task_run_started
)
from security.tests import capture_security_logs

from apps.test_security.tasks import sum_task

from .base import BaseTestCaseMixin, test_call_command


@override_settings(SECURITY_BACKENDS={})
class CommandTestCase(BaseTestCaseMixin, ClientTestCase):

    SQL_LOG_MODELS = {
        'input-request': SQLInputRequestLog,
        'output-request': SQLOutputRequestLog,
        'command': SQLCommandLog,
        'celery-invocation': SQLCeleryTaskInvocationLog,
        'celery-run': SQLCeleryTaskRunLog,
    }

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'sql'}, SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS={'sql_purge_logs'})
    def test_sql_purge_logs_should_remove_logged_data(self):
        responses.add(responses.GET, 'https://localhost/test', body='test')

        test_call_command('test_command')
        sum_task.apply(args=(5, 8))
        assert_http_ok(self.get('/home/'))
        requests.get('https://localhost/test')

        sql_type_model = {
            ('input-request', SQLInputRequestLog),
            ('output-request', SQLOutputRequestLog),
            ('command', SQLCommandLog),
            ('celery-invocation', SQLCeleryTaskInvocationLog),
            ('celery-run', SQLCeleryTaskRunLog),
        }

        for log_type, log_model in sql_type_model:
            test_call_command('sql_purge_logs', type=log_type, interactive=False, expiration='1d')
            assert_equal(log_model.objects.count(), 1)

            with freeze_time(now() + timedelta(days=1, minutes=1)):
                test_call_command('sql_purge_logs', type=log_type, interactive=False, expiration='1d')
                assert_equal(log_model.objects.count(), 0)

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'elasticsearch'},
                       SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS={'elasticsearch_purge_logs'})
    def test_elasticsearch_purge_logs_should_remove_logged_data(self):
        responses.add(responses.GET, 'https://localhost/test', body='test')

        with capture_security_logs() as logged_data:
            test_call_command('test_command')
            sum_task.apply(args=(5, 8))
            assert_http_ok(self.get('/home/'))
            requests.get('https://localhost/test')

            elasticsearch_type_model_receivers = (
                ('input-request', ElasticsearchInputRequestLog, 'input_request'),
                ('output-request', ElasticsearchOutputRequestLog, 'output_request'),
                ('command', ElasticsearchCommandLog, 'command'),
                ('celery-invocation', ElasticsearchCeleryTaskInvocationLog, 'celery_task_invocation'),
                ('celery-run', ElasticsearchCeleryTaskRunLog, 'celery_task_run'),
            )

            for log_type, log_model, log_data_name in elasticsearch_type_model_receivers:
                test_call_command('elasticsearch_purge_logs', type=log_type, interactive=False, expiration='1d')
                log_model._index.refresh()
                assert_equal(log_model.search().filter(
                    'ids', values=[logged_data[log_data_name][0].id]
                ).count(), 1)

                with freeze_time(now() + timedelta(days=1, minutes=1)):
                    test_call_command('elasticsearch_purge_logs', type=log_type, interactive=False, expiration='1d')
                    log_model._index.refresh()
                    assert_equal(log_model.search().filter(
                        'ids', values=[logged_data[log_data_name][0].id]
                    ).count(), 0)
