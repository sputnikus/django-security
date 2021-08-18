import json

import responses

from django import get_version
from django.test import override_settings
from django.utils.encoding import force_text

from germanium.decorators import data_consumer
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_equal, assert_false, assert_http_not_found, assert_http_ok, assert_http_redirect,
    assert_http_too_many_requests, assert_in, assert_is_none, assert_is_not_none, assert_not_in,
    assert_raises, assert_true, assert_equal_model_fields
)


from security.enums import RequestLogState
from security.config import settings
from security.decorators import log_with_data
from security.backends.sql.models import InputRequestLog as SQLInputRequestLog
from security.backends.elasticsearch.models import InputRequestLog as ElasticsearchInputRequestLog

from security import requests
from security.backends.signals import (
    input_request_started, input_request_finished, input_request_error, output_request_started, output_request_finished
)

from .base import BaseTestCaseMixin, _all_, TRUNCATION_CHAR, assert_equal_dict_data, set_signal_receiver


@override_settings(SECURITY_BACKENDS={}, SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES=None)
class InputRequestLogTestCase(BaseTestCaseMixin, ClientTestCase):

    def test_input_request_to_homepage_should_be_logged(self):
        expected_input_request_started_data = {
            'request_headers': {'COOKIE': '[Filtered]'},
            'request_body': '',
            'user_id': None,
            'method': 'GET',
            'host': 'testserver',
            'path': '/home/',
            'queries': {'name': 'value'},
            'is_secure': False,
            'ip': '127.0.0.1',
            'start': _all_,
            'view_slug': 'home'
        }
        expected_input_request_finished_data = {
            **expected_input_request_started_data,
            'stop': _all_,
            'response_code': 200,
            'response_headers': {'Content-Type': 'text/html; charset=utf-8', 'X-Frame-Options': 'DENY'},
            'response_body': 'home page response',
        }
        with set_signal_receiver(input_request_started, expected_input_request_started_data) as started_receiver:
            with set_signal_receiver(input_request_finished, expected_input_request_finished_data) as finish_receiver:
                with set_signal_receiver(input_request_error) as error_receiver:
                    assert_http_ok(self.get('/home/?name=value'))
                    assert_equal(started_receiver.calls, 1)
                    assert_equal(finish_receiver.calls, 1)
                    assert_equal(error_receiver.calls, 0)

    @data_consumer('create_user')
    def test_input_request_to_login_page_should_be_logged(self, user):
        expected_input_request_started_data = {
            'request_headers': {'COOKIE': '[Filtered]'},
            'request_body': (
                '--BoUnDaRyStRiNg\r\n'
                'Content-Disposition: form-data; name="username"\r\n'
                '\r\n'
                'test\r\n'
                '--BoUnDaRyStRiNg\r\n'
                '[Filtered]\n'
                '--BoUnDaRyStRiNg--\r\n'
            ),
            'user_id': None,
            'method': 'POST',
            'host': 'testserver',
            'path': '/admin/login/',
            'queries': {},
            'is_secure': False,
            'ip': '127.0.0.1',
            'start': _all_,
            'view_slug': 'admin:login'
        }
        expected_input_request_finished_data = {
            **expected_input_request_started_data,
            'stop': _all_,
            'response_code': 302,
            'response_headers': {
                'Cache-Control': 'max-age=0, no-cache, no-store, must-revalidate, private',
                'Content-Type': 'text/html; charset=utf-8',
                'Expires': _all_,
                'Location': '/accounts/profile/',
                'Vary': 'Cookie',
                'X-Frame-Options': 'DENY'
            },
            'response_body': '',
            'user_id': user.pk,
        }
        with set_signal_receiver(input_request_started, expected_input_request_started_data) as started_receiver:
            with set_signal_receiver(input_request_finished, expected_input_request_finished_data) as finish_receiver:
                assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
                assert_equal(started_receiver.calls, 1)
                assert_equal(finish_receiver.calls, 1)

    def test_input_request_to_error_page_should_be_logged(self):
        expected_input_request_started_data = {
            'request_headers': {'COOKIE': '[Filtered]'},
            'request_body': '',
            'user_id': None,
            'method': 'GET',
            'host': 'testserver',
            'path': '/error/',
            'queries': {},
            'is_secure': False,
            'ip': '127.0.0.1',
            'start': _all_,
            'view_slug': 'apps.test_security.views.error_view'
        }
        expected_input_request_error_data = {
            **expected_input_request_started_data,
            'error_message': _all_,
        }
        expected_input_request_finished_data = {
            **expected_input_request_error_data,
            'stop': _all_,
            'response_code': 500,
            'response_headers': _all_,
            'response_body': _all_,
        }
        with set_signal_receiver(input_request_started, expected_input_request_started_data) as started_receiver:
            with set_signal_receiver(input_request_error, expected_input_request_error_data) as error_receiver:
                with set_signal_receiver(input_request_finished, expected_input_request_finished_data) as finish_receiver:
                    with assert_raises(RuntimeError):
                        assert_http_ok(self.get('/error/'))
                    assert_equal(started_receiver.calls, 1)
                    assert_equal(error_receiver.calls, 1)
                    assert_equal(finish_receiver.calls, 1)

    @override_settings(SECURITY_LOG_REQUEST_IGNORE_IP=('127.0.0.1',))
    def test_ignored_client_ip_should_not_be_logged(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            assert_http_ok(self.get('/home/'))
            assert_equal(started_receiver.calls, 0)

    @override_settings(SECURITY_LOG_REQUEST_IGNORE_URL_PATHS=('/home/',))
    def test_ignored_client_ip_should_not_be_logged(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            assert_http_ok(self.get('/home/'))
            assert_equal(started_receiver.calls, 0)

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=10)
    def test_request_body_should_be_truncated(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            self.post('/admin/login/', data={'username': 20 * 'a', 'password': 20 * 'b'})
            assert_equal(len(started_receiver.last_logger.data['request_body']), 10)
            assert_true(started_receiver.last_logger.data['request_body'].endswith(TRUNCATION_CHAR))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_LENGTH=10)
    def test_response_body_should_be_truncated(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            self.post('/admin/login/', data={'username': 20 * 'a', 'password': 20 * 'b'})
            assert_equal(len(started_receiver.last_logger.data['response_body']), 10)
            assert_true(started_receiver.last_logger.data['response_body'].endswith(TRUNCATION_CHAR))

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=None, SECURITY_HIDE_SENSITIVE_DATA=False)
    def test_request_body_truncation_should_be_turned_off(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            self.post('/admin/login/', data={'username': 2000 * 'a', 'password': 2000 * 'b'})
            assert_equal(len(started_receiver.last_logger.data['request_body']), 4162)
            assert_false(started_receiver.last_logger.data['request_body'].endswith(TRUNCATION_CHAR))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_LENGTH=None, SECURITY_HIDE_SENSITIVE_DATA=False)
    def test_response_body_truncation_should_be_turned_off(self):
        with set_signal_receiver(input_request_started) as started_receiver:
            response = self.post('/admin/login/', data={'username': 2000 * 'a', 'password': 2000 * 'b'})
            assert_equal(started_receiver.last_logger.data['response_body'], force_text(response.content))
            assert_false(started_receiver.last_logger.data['response_body'].endswith(TRUNCATION_CHAR))

    @override_settings(SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES=())
    def test_not_allowed_content_type_body_should_not_be_logged(self):
        with set_signal_receiver(input_request_finished) as finished_receiver:
            assert_http_ok(self.get('/home/'))
            assert_is_none(finished_receiver.last_logger.data['response_body'])

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=100, SECURITY_LOG_JSON_STRING_LENGTH=10)
    def test_json_request_data_should_be_truncated(self):
        with set_signal_receiver(input_request_finished) as finished_receiver:
            self.c.post('/admin/login/', data=json.dumps({'a': 50 * 'a', 'b': 50 * 'b'}),
                        content_type='application/json')
            assert_equal(
                json.loads(finished_receiver.last_logger.data['request_body']),
                json.loads('{"a": "%s%s", "b": "%s%s"}' % (
                    9 * 'a', TRUNCATION_CHAR, 9 * 'b', TRUNCATION_CHAR
                ))
            )

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=50, SECURITY_LOG_JSON_STRING_LENGTH=None)
    def test_json_request_data_should_not_be_truncated(self):
        with set_signal_receiver(input_request_finished) as finished_receiver:
            self.c.post('/admin/login/', data=json.dumps({'a': 50 * 'a'}),
                        content_type='application/json')
            assert_equal(finished_receiver.last_logger.data['request_body'], '{"a": "' + 42 * 'a' + TRUNCATION_CHAR)
            assert_true(finished_receiver.last_logger.data['request_body'].endswith(TRUNCATION_CHAR))

    @override_settings(SECURITY_LOG_REQUEST_BODY_LENGTH=100, SECURITY_LOG_JSON_STRING_LENGTH=10)
    def test_json_request_should_have_been_whole_truncated_values_and_inner_data_too(self):
        with set_signal_receiver(input_request_finished) as finished_receiver:
            self.c.post('/admin/login/', data=json.dumps({50 * 'a': 50 * 'a', 50 * 'b': 50 * 'b'}),
                        content_type='application/json')
            assert_equal(len(finished_receiver.last_logger.data['request_body']), 100)
            assert_true(finished_receiver.last_logger.data['request_body'].endswith(TRUNCATION_CHAR))

    @responses.activate
    def test_output_request_should_be_logged_with_input_request(self):
        with set_signal_receiver(input_request_started) as input_request_started_receiver:
            with set_signal_receiver(output_request_started) as output_request_started_receiver:
                with set_signal_receiver(output_request_finished) as output_request_finished_receiver:
                    responses.add(responses.GET, 'http://test.cz', body='test')
                    assert_equal(self.get('/proxy/?url=http://test.cz').content, b'test')
                    assert_equal(output_request_started_receiver.calls, 1)
                    assert_equal(output_request_finished_receiver.calls, 1)
                    assert_equal(
                        output_request_started_receiver.last_logger.parent_with_id,
                        input_request_started_receiver.last_logger
                    )

    @responses.activate
    @data_consumer('create_user')
    def test_output_logged_request_should_be_related_with_object(self, user):
        with set_signal_receiver(output_request_finished) as output_request_finished_receiver:
            assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
            responses.add(responses.GET, 'http://test.cz', body='test')
            assert_equal(self.get('/proxy/?url=http://test.cz').content, b'test')
            assert_equal(len(output_request_finished_receiver.last_logger.related_objects), 1)
            assert_equal(list(output_request_finished_receiver.last_logger.related_objects)[0], user)

    @responses.activate
    @data_consumer('create_user')
    def test_input_logged_request_should_have_set_data(self, user):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
            assert_http_ok(self.get('/home/'))
            assert_equal(len(input_request_finished_receiver.last_logger.related_objects), 1)
            assert_equal(list(input_request_finished_receiver.last_logger.related_objects)[0], user)
            assert_equal(input_request_finished_receiver.last_logger.slug, 'user-home')

    @data_consumer('create_user')
    @override_settings(SECURITY_SENSITIVE_DATA_REPLACEMENT='(Filtered)')
    def test_sensitive_replacement_should_be_changed(self, user):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
            assert_equal(input_request_finished_receiver.last_logger.data['request_headers']['COOKIE'], '(Filtered)')

    def test_sensitive_queries_should_be_hidden(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            assert_http_ok(self.get('/home/?token=test'))
            assert_equal(input_request_finished_receiver.last_logger.data['queries']['token'], '[Filtered]')

    @data_consumer('create_user')
    def test_sensitive_headers_should_be_hidden(self, user):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            assert_http_redirect(self.post('/admin/login/', data={'username': 'test', 'password': 'test'}))
            assert_equal(input_request_finished_receiver.last_logger.data['request_headers']['COOKIE'], '[Filtered]')

    def test_sensitive_data_body_in_raw_form_should_be_hidden(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            self.post('/admin/login/', data={'username': 'test', 'password': 'secret-password\nddd'})
            assert_in('[Filtered]', input_request_finished_receiver.last_logger.data['request_body'])

    def test_sensitive_data_body_in_json_should_be_hidden(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            self.c.post('/admin/login/', data=json.dumps({'username': 'test', 'password': 'secret-password'}),
                        content_type='application/json')
            assert_in('"password": "[Filtered]"', input_request_finished_receiver.last_logger.data['request_body'])
            assert_not_in(
                '"password": "secret-password"', input_request_finished_receiver.last_logger.data['request_body']
            )

    @override_settings(SECURITY_BACKENDS={'sql'})
    @data_consumer('create_user')
    def test_input_request_to_homepage_should_be_logged_in_sql_backend(self, user):
        with log_with_data(related_objects=[user]):
            assert_http_ok(self.get('/home/?name=value'))
            assert_equal(SQLInputRequestLog.objects.count(), 1)
            sql_input_request_log = SQLInputRequestLog.objects.get()
            assert_equal_model_fields(
                sql_input_request_log,
                request_headers={'COOKIE': '[Filtered]'},
                request_body='',
                user_id=None,
                method='GET',
                host='testserver',
                path='/home/',
                queries={'name': 'value'},
                is_secure=False,
                ip='127.0.0.1',
                view_slug='home',
                slug=None,
                time=(sql_input_request_log.stop - sql_input_request_log.start).total_seconds(),
                extra_data={},
                error_message=None,
                response_code=200,
                response_headers={'Content-Type': 'text/html; charset=utf-8', 'X-Frame-Options': 'DENY'},
                response_body='home page response',
                state=RequestLogState.INFO,
            )
            assert_equal([rel_obj.object for rel_obj in sql_input_request_log.related_objects.all()], [user])

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @data_consumer('create_user')
    def test_input_request_to_homepage_should_be_logged_in_elasticsearch_backend(self, user):
        with log_with_data(related_objects=[user]):
            with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
                assert_http_ok(self.get('/home/?name=value'))
                elasticsearch_input_request_log = ElasticsearchInputRequestLog.get(
                    id=input_request_finished_receiver.last_logger.id
                )
                assert_equal_model_fields(
                    elasticsearch_input_request_log,
                    request_headers='{"COOKIE": "[Filtered]"}',
                    request_body='',
                    user_id=None,
                    method='GET',
                    host='testserver',
                    path='/home/',
                    queries='{"name": "value"}',
                    is_secure=False,
                    ip='127.0.0.1',
                    view_slug='home',
                    slug=None,
                    time=(elasticsearch_input_request_log.stop - elasticsearch_input_request_log.start).total_seconds(),
                    extra_data=None,
                    error_message=None,
                    response_code=200,
                    response_headers='{"Content-Type": "text/html; charset=utf-8", "X-Frame-Options": "DENY"}',
                    response_body='home page response',
                    state=RequestLogState.INFO,
                )
                assert_equal(
                    [rel_obj for rel_obj in elasticsearch_input_request_log.related_objects],
                    ['default|3|{}'.format(user.id)]
                )

    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_input_request_to_homepage_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            with self.assertLogs('security.input_request', level='INFO') as cm:
                assert_http_ok(self.get('/home/?name=value'))
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.input_request:'
                        f'Input request "{input_request_finished_receiver.last_logger.id}" '
                        f'to "testserver" with path "/home/" is started',
                        f'INFO:security.input_request:'
                        f'Input request "{input_request_finished_receiver.last_logger.id}" '
                        f'to "testserver" with path "/home/" is finished'
                    ]
                )

    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_input_request_to_error_page_should_be_logged_in_sql_backend(self):
        with assert_raises(RuntimeError):
            self.get('/error/')
        assert_equal(SQLInputRequestLog.objects.count(), 1)
        sql_input_request_log = SQLInputRequestLog.objects.get()
        assert_equal_model_fields(
            sql_input_request_log,
            method='GET',
            path='/error/',
            time=(sql_input_request_log.stop - sql_input_request_log.start).total_seconds(),
            response_code=500,
            state=RequestLogState.ERROR,
        )
        assert_is_not_none(sql_input_request_log.error_message)

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    def test_input_request_to_error_page_should_be_logged_in_elasticsearch_backend(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            with assert_raises(RuntimeError):
                self.get('/error/')
            elasticsearch_input_request_log = ElasticsearchInputRequestLog.get(
                id=input_request_finished_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_input_request_log,
                method='GET',
                path='/error/',
                time=(elasticsearch_input_request_log.stop - elasticsearch_input_request_log.start).total_seconds(),
                response_code=500,
                state=RequestLogState.ERROR,
            )
            assert_is_not_none(elasticsearch_input_request_log.error_message)

    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_input_request_to_error_page_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            with self.assertLogs('security.input_request', level='INFO') as cm:
                with assert_raises(RuntimeError):
                    self.get('/error/')
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.input_request:'
                        f'Input request "{input_request_finished_receiver.last_logger.id}" '
                        f'to "testserver" with path "/error/" is started',
                        f'ERROR:security.input_request:'
                        f'Input request "{input_request_finished_receiver.last_logger.id}" '
                        f'to "testserver" with path "/error/" is raised exception',
                        f'INFO:security.input_request:'
                        f'Input request "{input_request_finished_receiver.last_logger.id}" '
                        f'to "testserver" with path "/error/" is finished'
                    ]
                )

    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_input_request_to_404_page_should_be_logged_in_sql_backend(self):
        assert_http_not_found(self.get('/404/'))
        assert_equal(SQLInputRequestLog.objects.count(), 1)
        sql_input_request_log = SQLInputRequestLog.objects.get()
        assert_equal_model_fields(
            sql_input_request_log,
            response_code=404,
            state=RequestLogState.WARNING,
        )

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    def test_input_request_to_404_page_should_be_logged_in_elasticsearch_backend(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            assert_http_not_found(self.get('/404/'))
            elasticsearch_input_request_log = ElasticsearchInputRequestLog.get(
                id=input_request_finished_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_input_request_log,
                response_code=404,
                state=RequestLogState.WARNING,
            )

    def test_decorated_view_with_hide_request_body_should_not_log_request_body(self):
        with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
            self.post('/hide-request-body/', data={'a': 20 * 'a', 'b': 20 * 'b'})
            assert_equal(input_request_finished_receiver.last_logger.data['request_body'], '[Filtered]')

    def test_decorated_view_with_log_exempt_should_not_log_request(self):
        with set_signal_receiver(input_request_started) as input_request_started_receiver:
            with set_signal_receiver(input_request_finished) as input_request_finished_receiver:
                self.get('/log-exempt/')
                assert_equal(input_request_started_receiver.calls, 0)
                assert_equal(input_request_finished_receiver.calls, 0)

    def test_throttling_should_not_be_raised(self):
        for _ in range(100):
            assert_http_redirect(self.get('/admin/'))

    @override_settings(SECURITY_BACKENDS={'sql'})
    @override_settings(SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH='apps.test_security.tests.sql_throttling_validators')
    def test_throttling_configuration_with_sql_validators_should_be_changed_via_settings(self):
        for _ in range(2):
            assert_http_redirect(self.get('/admin/'))
        assert_http_too_many_requests(self.get('/admin/'))

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @override_settings(
        SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH='apps.test_security.tests.elasticsearch_throttling_validators'
    )
    def test_throttling_configuration_with_elasticsearch_validators_should_be_changed_via_settings(self):
        for _ in range(2):
            assert_http_redirect(self.get('/admin/'))
            ElasticsearchInputRequestLog._index.refresh()
        assert_http_too_many_requests(self.get('/admin/'))

    @override_settings(SECURITY_BACKENDS={'sql'})
    @override_settings(SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH='apps.test_security.tests.sql_throttling_validators')
    def test_decorated_view_with_throttling_exempt_should_not_raise_throttling_exception(self):
        for _ in range(20):
            assert_http_ok(self.get('/throttling-exempt/'))
        assert_http_ok(self.get('/throttling-exempt/'))

    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_decorated_view_with_throttling_should_raise_throttling_exception(self):
        assert_http_ok(self.get('/extra-throttling/'))
        assert_http_too_many_requests(self.get('/extra-throttling/'))

    @data_consumer('create_user')
    def test_slug_and_related_data_should_be_send_to_input_request_logger(self, user):
        with log_with_data(related_objects=[user], slug='TEST'):
            with set_signal_receiver(input_request_started) as started_receiver:
                assert_http_ok(self.get('/home/'))
                assert_equal(started_receiver.last_logger.related_objects, {user})
                assert_equal(started_receiver.last_logger.slug, 'TEST')
