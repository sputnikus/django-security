import io
import json

from datetime import timedelta

from celery.exceptions import CeleryError, TimeoutError

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.db import transaction
from django.utils.timezone import now

import responses

from freezegun import freeze_time

from security.models import (
    InputLoggedRequest, OutputLoggedRequest, CommandLog, LoggedRequestStatus, CeleryTaskLog, CeleryTaskRunLog,
    CeleryTaskLogState, CeleryTaskRunLogState
)
from security.management import call_command
from security.transport import security_requests as requests
from security.transport.transaction import (
    atomic_log, log_request_related_objects, get_all_request_related_objects, get_request_slug
)
from security.tasks import call_django_command

from germanium.decorators import data_provider
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_in, assert_not_in, assert_equal, assert_true, assert_false, assert_http_redirect, assert_http_bad_request,
    assert_http_application_error, assert_http_ok, assert_http_not_found, assert_raises, assert_http_too_many_requests,
    assert_is_not_none, assert_raises, assert_is_none, assert_not_raises
)

from apps.test_security.tasks import sum_task, error_task, retry_task, unique_task


class TestException(Exception):
    pass


class BaseTestCaseMixin:

    def create_user(self, username='test', email='test@test.cz'):
        return User.objects._create_user(username, email, 'test', is_staff=True, is_superuser=True)


class SecurityTestCase(BaseTestCaseMixin, ClientTestCase):

    def test_every_request_should_be_logged(self):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        self.get('/')
        assert_equal(InputLoggedRequest.objects.count(), 1)

    @data_provider('create_user')
    def test_data_change_should_be_connected_with_logged_request(self, user):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
        assert_equal(InputLoggedRequest.objects.count(), 1)
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(
            input_logged_request.input_logged_request_revisions.get().revision.version_set.get().content_type,
            ContentType.objects.get_for_model(User)
        )

    @data_provider('create_user')
    def test_input_logged_request_should_have_right_status(self, user):
        assert_http_ok(self.post('/admin/login/', data={'username': 'invalid', 'password': 'invalid'}))
        assert_equal(InputLoggedRequest.objects.first().status, LoggedRequestStatus.INFO)
        assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
        assert_equal(InputLoggedRequest.objects.first().status, LoggedRequestStatus.INFO)
        assert_raises(Exception, self.get, '/proxy/')
        assert_equal(InputLoggedRequest.objects.first().status, LoggedRequestStatus.ERROR)
        assert_http_not_found(self.get('/404/'))
        assert_equal(InputLoggedRequest.objects.first().status, LoggedRequestStatus.WARNING)

    @override_settings(SECURITY_LOG_REQUEST_IGNORE_IP=('127.0.0.1',))
    def test_ignored_client_ip_should_not_be_logged(self):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        self.get('/')
        assert_equal(InputLoggedRequest.objects.count(), 0)

    @override_settings(SECURITY_LOG_REQUEST_IGNORE_URL_PATHS=('/',))
    def test_ignored_request_path_should_not_be_logged(self):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        self.get('/')
        assert_equal(InputLoggedRequest.objects.count(), 0)

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=10)
    def test_request_body_should_be_truncated(self):
        self.post('/admin/login/', data={'username': 20 * 'a', 'password': 20 * 'b'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(len(input_logged_request.request_body), 10)
        assert_true(input_logged_request.request_body.endswith('…'))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_LENGTH=10)
    def test_response_body_should_be_truncated(self):
        self.post('/admin/login/', data={'username': 20 * 'a', 'password': 20 * 'b'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(len(input_logged_request.response_body), 10)
        assert_true(input_logged_request.response_body.endswith('…'))

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=None)
    def test_request_body_truncation_should_be_turned_off(self):
        self.post('/admin/login/', data={'username': 2000 * 'a', 'password': 2000 * 'b'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(len(input_logged_request.request_body), 4183)
        assert_false(input_logged_request.request_body.endswith('…'))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_LENGTH=None)
    def test_response_body_truncation_should_be_turned_off(self):
        resp = self.post('/admin/login/', data={'username': 20 * 'a', 'password': 20 * 'b'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(input_logged_request.response_body, str(resp.content))
        assert_false(input_logged_request.response_body.endswith('…'))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES=())
    def test_not_allowed_content_type_should_not_be_logged(self):
        self.get('/')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_false(input_logged_request.response_body)

    @override_settings(SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES=None)
    def test_allowed_content_type_should_be_turned_off(self):
        self.get('/')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_false(input_logged_request.response_body)

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=100, SECURITY_LOG_JSON_STRING_LENGTH=10)
    def test_json_request_should_be_truncated_with_another_method(self):
        self.c.post('/admin/login/', data=json.dumps({'a': 50 * 'a', 'b': 50 * 'b'}),
                    content_type='application/json')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(
            json.loads(input_logged_request.request_body),
            json.loads('{"a": "aaaaaaaaa…", "b": "bbbbbbbbb…"}')
        )
        assert_false(input_logged_request.request_body.endswith('…'))

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=50, SECURITY_LOG_JSON_STRING_LENGTH=None)
    def test_json_request_should_not_be_truncated_with_another_method(self):
        self.c.post('/admin/login/', data=json.dumps({'a': 50 * 'a'}),
                    content_type='application/json')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(input_logged_request.request_body, '{"a": "' + 42* 'a' + '…')
        assert_true(input_logged_request.request_body.endswith('…'))

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=100, SECURITY_LOG_JSON_STRING_LENGTH=10)
    def test_json_request_should_be_truncated_with_another_method_and_standard_method_too(self):
        self.c.post('/admin/login/', data=json.dumps({50 * 'a': 50 * 'a', 50 * 'b': 50 * 'b'}),
                    content_type='application/json')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(len(input_logged_request.request_body), 100)
        assert_true(input_logged_request.request_body.endswith('…'))

    def test_response_with_exception_should_be_logged(self):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        assert_raises(Exception, self.get, '/proxy/')
        assert_equal(InputLoggedRequest.objects.count(), 1)

    @responses.activate
    def test_response_with_exception_should_be_logged(self):
        responses.add(responses.GET, 'http://test.cz', body='test')
        assert_equal(self.get('/proxy/?url=http://test.cz').content, b'test')
        assert_equal(InputLoggedRequest.objects.count(), 1)
        assert_equal(OutputLoggedRequest.objects.count(), 1)

    @responses.activate
    @data_provider('create_user')
    def test_output_logged_request_should_be_related_with_object(self, user):
        assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
        responses.add(responses.GET, 'http://test.cz', body='test')
        assert_equal(self.get('/proxy/?url=http://test.cz').content, b'test')
        assert_equal(InputLoggedRequest.objects.count(), 2)
        assert_equal(OutputLoggedRequest.objects.count(), 1)
        output_logged_request = OutputLoggedRequest.objects.get()
        assert_equal(output_logged_request.related_objects.get().object, user)

    def test_sensitive_data_body_in_json_should_be_hidden(self):
        self.c.post('/admin/login/', data=json.dumps({'username': 'test', 'password': 'secret-password'}),
                    content_type='application/json')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_in('"password": "[Filtered]"', input_logged_request.request_body)
        assert_not_in('"password": "secret-password"', input_logged_request.request_body)

    def test_sensitive_data_body_in_raw_form_should_be_hidden(self):
        self.post('/admin/login/', data={'username': 'test', 'password': 'secret-password\nddd'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_in('[Filtered]', input_logged_request.request_body)

    @data_provider('create_user')
    def test_sensitive_headers_should_be_hidden(self, user):
        assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(input_logged_request.request_headers['COOKIE'], '[Filtered]')

    def test_sensitive_queries_should_be_hidden(self):
        self.get('/?token=test')
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(input_logged_request.queries['token'], '[Filtered]')

    @data_provider('create_user')
    @override_settings(SECURITY_SENSITIVE_DATA_REPLACEMENT='(Filtered)')
    def test_sensitive_replacement_should_be_changed(self, user):
        assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
        input_logged_request = InputLoggedRequest.objects.get()
        assert_equal(input_logged_request.request_headers['COOKIE'], '(Filtered)')

    @override_settings(SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS=())
    def test_command_should_be_logged(self):
        assert_equal(CommandLog.objects.count(), 0)
        call_command('showmigrations', stdout=io.StringIO(), stderr=io.StringIO())
        assert_equal(CommandLog.objects.count(), 1)

    @override_settings(SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS=('showmigrations',))
    def test_excluded_command_should_not_be_logged(self):
        assert_equal(CommandLog.objects.count(), 0)
        call_command('showmigrations', stdout=io.StringIO(), stderr=io.StringIO())
        assert_equal(CommandLog.objects.count(), 0)

    def test_throttling_should_be_raised(self):
        for _ in range(20):
            assert_http_redirect(self.get('/admin/'))
        assert_http_too_many_requests(self.get('/admin/'))

    @override_settings(SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH='apps.test_security.tests.throttling_validators')
    def test_throttling_configuration_should_be_changed_via_settings(self):
        for _ in range(2):
            assert_http_redirect(self.get('/admin/'))
        assert_http_too_many_requests(self.get('/admin/'))

    def test_decorated_view_with_hide_request_body_should_not_log_request_body(self):
        self.post('/hide-request-body/', data={'a': 20 * 'a', 'b': 20 * 'b'})
        input_logged_request = InputLoggedRequest.objects.get()
        assert_false(input_logged_request.request_body)

    def test_decorated_view_with_log_exempt_should_not_log_request(self):
        self.get('/log-exempt/')
        assert_equal(InputLoggedRequest.objects.count(), 0)

    def test_decorated_view_with_throttling_exempt_should_not_raise_throttling_exception(self):
        for _ in range(20):
            assert_http_ok(self.get('/throttling-exempt/'))
        assert_http_ok(self.get('/throttling-exempt/'))

    def test_decorated_view_with_throttling_should_raise_throttling_exception(self):
        assert_http_ok(self.get('/extra-throttling/'))
        assert_http_too_many_requests(self.get('/extra-throttling/'))

    @responses.activate
    def test_output_logged_requests_with_atomic_block_should_not_be_logged_if_exception_is_raised(self):
        responses.add(responses.GET, 'http://test.cz', body='test')
        with assert_raises(TestException):
            with transaction.atomic():
                requests.get('http://test.cz')
                assert_equal(OutputLoggedRequest.objects.count(), 1)
                raise TestException
        assert_equal(OutputLoggedRequest.objects.count(), 0)

    @responses.activate
    def test_output_logged_requests_with_atomic_and_log_atomic_block_should_be_logged_if_exception_is_raised(self):
        responses.add(responses.GET, 'http://test.cz', body='test')
        with assert_raises(TestException):
            with atomic_log():
                with transaction.atomic():
                    requests.get('http://test.cz')
                    assert_equal(OutputLoggedRequest.objects.count(), 0)
                    raise TestException
        assert_equal(OutputLoggedRequest.objects.count(), 1)

    @responses.activate
    def test_output_logged_requests_with_atomic_and_log_atomic_block_should_be_nested(self):
        responses.add(responses.GET, 'http://test.cz', body='test')
        with assert_raises(TestException):
            with atomic_log():
                with transaction.atomic():
                    requests.get('http://test.cz')
                    with atomic_log():
                        with transaction.atomic():
                            requests.get('http://test.cz')
                    assert_equal(OutputLoggedRequest.objects.count(), 0)
                    raise TestException
        assert_equal(OutputLoggedRequest.objects.count(), 2)

    @responses.activate
    def test_response_sensitive_data_body_in_json_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        requests.post('http://test.cz', data=json.dumps({'password': 'secret-password'}))
        output_logged_requst = OutputLoggedRequest.objects.get()
        assert_in('"password": "[Filtered]"', output_logged_requst.request_body)
        assert_not_in('"password": "secret-password"', output_logged_requst.request_body)
        assert_in('"password": "secret-password"', responses.calls[0].request.body)
        assert_not_in('"password": "[Filtered]"', responses.calls[0].request.body)

    @responses.activate
    def test_response_sensitive_headers_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        requests.post('http://test.cz', headers={'token': 'secret'})
        output_logged_request = OutputLoggedRequest.objects.get()
        assert_equal(output_logged_request.request_headers['token'], '[Filtered]')
        assert_equal(responses.calls[0].request.headers['token'], 'secret')

    @responses.activate
    def test_response_sensitive_params_data_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        requests.post('http://test.cz', params={'token': 'secret'})
        output_logged_request = OutputLoggedRequest.objects.get()
        assert_equal(output_logged_request.queries['token'], '[Filtered]')
        assert_equal(responses.calls[0].request.url, 'http://test.cz/?token=secret')

    @responses.activate
    def test_response_more_sensitive_params_data_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        requests.post('http://test.cz', params={'token': ['secret', 'secret2']})
        output_logged_request = OutputLoggedRequest.objects.get()
        assert_equal(output_logged_request.queries['token'], ['[Filtered]', '[Filtered]'])
        assert_equal(responses.calls[0].request.url, 'http://test.cz/?token=secret&token=secret2')

    @responses.activate
    def test_response_sensitive_params_and_url_query_together_data_should_be_logged(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        requests.post('http://test.cz?a=1&a=2', params={'b': '6', 'a': '3', 'c': ['5']})
        output_logged_request = OutputLoggedRequest.objects.get()
        assert_equal(output_logged_request.queries, {'b': '6', 'a': ['3', '1', '2'], 'c': '5'})

    def test_celery_task_should_be_logged(self):
        sum_task.apply_async(args=(5, 8))
        assert_equal(CeleryTaskLog.objects.count(), 1)
        assert_equal(CeleryTaskLog.objects.get().get_state(), CeleryTaskLogState.SUCCEEDED)
        assert_equal(CeleryTaskRunLog.objects.count(), 1)
        assert_equal(CeleryTaskRunLog.objects.get().state, CeleryTaskRunLogState.SUCCEEDED)

    def test_celery_task_should_be_able_to_run_with_apply_async_on_commit(self):
        sum_task.apply_async_on_commit(args=(5, 8))
        assert_equal(CeleryTaskLog.objects.count(), 1)
        assert_equal(CeleryTaskLog.objects.get().get_state(), CeleryTaskLogState.SUCCEEDED)
        assert_equal(CeleryTaskRunLog.objects.count(), 1)
        assert_equal(CeleryTaskRunLog.objects.get().state, CeleryTaskRunLogState.SUCCEEDED)

    def test_celery_error_task_should_be_set_as_failed_in_the_log(self):
        error_task.apply_async_on_commit()
        assert_equal(CeleryTaskLog.objects.count(), 1)
        assert_equal(CeleryTaskLog.objects.get().get_state(), CeleryTaskLogState.FAILED)
        assert_equal(CeleryTaskRunLog.objects.count(), 1)
        assert_equal(CeleryTaskRunLog.objects.get().state, CeleryTaskRunLogState.FAILED)
        assert_is_not_none(CeleryTaskRunLog.objects.get().error_message)

    def test_django_command_should_be_run_via_task(self):
        call_django_command.apply_async(args=('check',))
        assert_equal(CeleryTaskLog.objects.count(), 1)
        assert_equal(CeleryTaskLog.objects.get().get_state(), CeleryTaskLogState.SUCCEEDED)
        assert_equal(CeleryTaskRunLog.objects.count(), 1)
        assert_equal(CeleryTaskRunLog.objects.get().state, CeleryTaskRunLogState.SUCCEEDED)

    def test_retry_command_should_be_automatically_retried(self):
        retry_task.apply_async()
        assert_equal(CeleryTaskLog.objects.count(), 1)
        assert_equal(CeleryTaskLog.objects.get().get_state(), CeleryTaskLogState.SUCCEEDED)
        assert_equal(CeleryTaskRunLog.objects.count(), 6)
        assert_equal(CeleryTaskRunLog.objects.values('celery_task_id').distinct().count(), 1)
        assert_equal(
            tuple(CeleryTaskRunLog.objects.order_by('created_at').values_list('state', flat=True)),
            (CeleryTaskRunLogState.RETRIED, CeleryTaskRunLogState.RETRIED, CeleryTaskRunLogState.RETRIED,
             CeleryTaskRunLogState.RETRIED, CeleryTaskRunLogState.RETRIED, CeleryTaskRunLogState.SUCCEEDED)
        )

    @freeze_time(now())
    def test_retry_command_should_be_delayed(self):
        retry_task.apply_async()
        assert_equal(CeleryTaskRunLog.objects.count(), 6)
        assert_equal(CeleryTaskLog.objects.first().estimated_time_of_first_arrival, now())
        assert_equal(
            tuple(CeleryTaskRunLog.objects.order_by('created_at').values_list('estimated_time_of_next_retry', flat=True)),
            (now() + timedelta(minutes=1), now() + timedelta(minutes=5),
             now() + timedelta(minutes=10), now() + timedelta(minutes=30), now() + timedelta(minutes=60), None)
        )

    @freeze_time(now())
    def test_retry_command_should_have_set_right_retry_value(self):
        retry_task.apply_async()
        assert_equal(CeleryTaskRunLog.objects.count(), 6)
        assert_equal(
            tuple(CeleryTaskRunLog.objects.order_by('created_at').values_list('retries', flat=True)),
            (0, 1, 2, 3, 4, 5)
        )

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30)
    def test_celery_task_should_have_rightly_set_stale_time(self):
        sum_task.apply_async(args=(5, 8))
        celery_task_log = CeleryTaskLog.objects.get()
        assert_equal(celery_task_log.estimated_time_of_first_arrival, now())
        assert_is_none(celery_task_log.expires)
        assert_equal(celery_task_log.stale, now() + timedelta(seconds=30))

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_celery_task_should_have_rightly_set_expires_time(self):
        sum_task.apply_async(args=(5, 8))
        celery_task_log = CeleryTaskLog.objects.get()
        assert_equal(celery_task_log.estimated_time_of_first_arrival, now())
        assert_equal(celery_task_log.expires, now() + timedelta(seconds=20))
        assert_equal(celery_task_log.stale, now() + timedelta(seconds=30))

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_celery_task_should_have_rightly_set_expires_time_if_soft_time_limit_is_set_in_task_call(self):
        sum_task.apply_async(args=(5, 8), time_limit=20)
        celery_task_log = CeleryTaskLog.objects.get()
        assert_equal(celery_task_log.estimated_time_of_first_arrival, now())
        assert_equal(celery_task_log.expires, now() + timedelta(seconds=10))
        assert_equal(celery_task_log.stale, now() + timedelta(seconds=30))

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_celery_task_should_have_rightly_set_expires_time_if_stale_time_limit_is_set_in_task_call(self):
        sum_task.apply_async(args=(5, 8), stale_time_limit=100)
        celery_task_log = CeleryTaskLog.objects.get()
        assert_equal(celery_task_log.estimated_time_of_first_arrival, now())
        assert_equal(celery_task_log.stale, now() + timedelta(seconds=100))
        assert_equal(celery_task_log.expires, now() + timedelta(seconds=90))

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_celery_task_should_have_rightly_set_expires_time_according_to_default_task_stale_limit_value(self):
        error_task.apply_async()
        celery_task_log = CeleryTaskLog.objects.get()
        assert_equal(celery_task_log.estimated_time_of_first_arrival, now())
        assert_equal(celery_task_log.stale, now() + timedelta(seconds=60*60))
        assert_equal(celery_task_log.expires, now() + timedelta(seconds=60 * 60 - 10))

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_stale_waiting_celery_task_should_be_set_as_failed_with_command(self):
        sum_task.apply_async(args=(5, 8))
        celery_task_log = CeleryTaskLog.objects.create(
            celery_task_id='random id',
            name='error_task',
            queue_name='default',
            input='',
            task_args=[],
            task_kwargs={},
            estimated_time_of_first_arrival=now() - timedelta(minutes=5),
            expires=now() - timedelta(minutes=4),
            stale=now() - timedelta(minutes=3)
        )
        call_command('set_stale_tasks_to_error_state')
        assert_equal(celery_task_log.refresh_from_db().get_state(), CeleryTaskLogState.EXPIRED)
        assert_false(CeleryTaskLog.objects.filter_stale().exists())

    @freeze_time(now())
    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=30, CELERYD_TASK_TIME_LIMIT=10)
    def test_stale_failed_celery_task_should_not_be_set_as_failed_with_command(self):
        sum_task.apply_async(args=(5, 8))
        celery_task_log = CeleryTaskLog.objects.create(
            celery_task_id='random id',
            name='error_task',
            queue_name='default',
            input='',
            task_args=[],
            task_kwargs={},
            estimated_time_of_first_arrival=now() - timedelta(minutes=5),
            expires=now() - timedelta(minutes=4),
            stale=now() - timedelta(minutes=3)
        )
        CeleryTaskRunLog.objects.create(
            celery_task_id='random id',
            name='error_task',
            state=CeleryTaskRunLogState.FAILED,
            task_args=[],
            task_kwargs={},
            retries=0
        )

        call_command('set_stale_tasks_to_error_state')
        assert_equal(celery_task_log.refresh_from_db().get_state(), CeleryTaskLogState.FAILED)

    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=None)
    def test_unique_task_shoud_have_set_stale_limit(self):
        with assert_raises(CeleryError):
            unique_task.delay()
        with override_settings(CELERYD_TASK_STALE_TIME_LIMIT=10):
            with assert_not_raises(CeleryError):
                unique_task.delay()

    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=5)
    def test_apply_async_and_get_result_should_return_time_error_for_zero_timeout(self):
        with assert_raises(TimeoutError):
            unique_task.apply_async_and_get_result(timeout=0)

    @override_settings(CELERYD_TASK_STALE_TIME_LIMIT=5)
    def test_apply_async_and_get_result_should_return_task_result(self):
        assert_equal(unique_task.apply_async_and_get_result(), 'unique')

    @responses.activate
    def test_output_logged_request_should_be_related_with_object_selected_in_decorator(self):
        user1 = self.create_user('test1', 'test1@test.cz')
        user2 = self.create_user('test2', 'test2@test.cz')

        responses.add(responses.GET, 'http://test.cz', body='test')
        assert_equal(get_all_request_related_objects(), [])
        with log_request_related_objects(slug='test1', related_objects=[user1]):
            assert_equal(set(get_all_request_related_objects()), {user1})

            requests.get('http://test.cz')
            assert_equal(OutputLoggedRequest.objects.count(), 1)
            assert_equal(OutputLoggedRequest.objects.get().related_objects.get().object, user1)
            assert_equal(OutputLoggedRequest.objects.first().slug, 'test1')
            with log_request_related_objects(slug='test2',related_objects=[user2]):
                assert_equal(set(get_all_request_related_objects()), {user1, user2})
                requests.get('http://test.cz')
                assert_equal(OutputLoggedRequest.objects.count(), 2)
                assert_equal(
                    {
                        related_object.object
                        for related_object in OutputLoggedRequest.objects.first().related_objects.all()
                    },
                    {user1, user2}
                )
                assert_equal(OutputLoggedRequest.objects.first().slug, 'test2')
            assert_equal(set(get_all_request_related_objects()), {user1})
            requests.get('http://test.cz')
            assert_equal(OutputLoggedRequest.objects.count(), 3)
            assert_equal(OutputLoggedRequest.objects.first().related_objects.get().object, user1)
            assert_equal(OutputLoggedRequest.objects.first().slug, 'test1')
        assert_equal(get_all_request_related_objects(), [])
        assert_is_none(get_request_slug())

    @data_provider('create_user')
    def test_task_log_is_processing_should_return_if_task_is_active_or_waiting(self, user):
        assert_false(sum_task.is_processing())

        celery_task_log = CeleryTaskLog.objects.create(
            celery_task_id='test',
            name='sum_task',
            stale=now(),
            estimated_time_of_first_arrival=now()
        )
        celery_task_log.related_objects.add(user)

        assert_true(sum_task.is_processing())
        assert_true(sum_task.is_processing(related_objects=[user]))

        user2 = self.create_user(username='test2', email='test2@test.cz')
        assert_false(sum_task.is_processing(related_objects=(user2,)))

        celery_task_run_log = CeleryTaskRunLog(
            celery_task_id='test',
            name='sum_task'
        )
        assert_true(sum_task.is_processing())
        assert_true(sum_task.is_processing(related_objects=[user]))

        celery_task_run_log.change_and_save(state=CeleryTaskRunLogState.SUCCEEDED)
        assert_false(sum_task.is_processing())

        celery_task_run_log.change_and_save(state=CeleryTaskRunLogState.FAILED)
        assert_false(sum_task.is_processing())

        celery_task_run_log.change_and_save(state=CeleryTaskRunLogState.RETRIED)
        assert_true(sum_task.is_processing())

        celery_task_run_log.change_and_save(state=CeleryTaskRunLogState.EXPIRED)
        assert_false(sum_task.is_processing())

        celery_task_run_log.change_and_save(state=CeleryTaskRunLogState.ACTIVE)
        assert_true(sum_task.is_processing())

        celery_task_log.change_and_save(is_set_as_stale=True)
        assert_false(sum_task.is_processing())
