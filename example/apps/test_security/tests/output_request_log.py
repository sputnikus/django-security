import json
import responses

from requests.exceptions import ConnectionError

from django.test import override_settings

from germanium.decorators import data_consumer
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_equal, assert_raises, assert_not_in, assert_in, assert_equal_model_fields, assert_is_not_none
)

from security import requests
from security.backends.signals import (
    output_request_started, output_request_finished, output_request_error
)
from security.decorators import log_with_data
from security.enums import RequestLogState
from security.backends.sql.models import OutputRequestLog as SQLOutputRequestLog
from security.backends.elasticsearch.models import OutputRequestLog as ElasticsearchOutputRequestLog

from .base import BaseTestCaseMixin, _all_, TRUNCATION_CHAR, assert_equal_dict_data, set_signal_receiver


@override_settings(SECURITY_BACKENDS={})
class OutputRequestLogTestCase(BaseTestCaseMixin, ClientTestCase):

    @responses.activate
    @data_consumer('create_user')
    def test_output_request_should_be_logged(self, user):
        responses.add(responses.POST, 'https://test.cz/test', body='test')
        expected_output_request_started_data = {
            'request_headers': {
                'User-Agent': 'python-requests/2.26.0',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Content-Length': '16'
            },
            'request_body': '{"test": "test"}',
            'method': 'POST',
            'host': 'test.cz',
            'path': '/test',
            'queries': {},
            'is_secure': True,
            'start': _all_,
        }
        expected_output_request_finished_data = {
            **expected_output_request_started_data,
            'stop': _all_,
            'response_code': 200,
            'response_headers': {'Content-Type': 'text/plain'},
            'response_body': 'test',
        }
        with set_signal_receiver(output_request_started, expected_output_request_started_data) as started_receiver:
            with set_signal_receiver(output_request_finished, expected_output_request_finished_data) as finish_receiver:
                with set_signal_receiver(output_request_error) as error_receiver:
                    requests.post(
                        'https://test.cz/test',
                        data=json.dumps({'test': 'test'}),
                        slug='test',
                        related_objects=[user]
                    )
                    assert_equal(started_receiver.calls, 1)
                    assert_equal(finish_receiver.calls, 1)
                    assert_equal(error_receiver.calls, 0)
                    assert_equal(started_receiver.last_logger.slug, 'test')
                    assert_equal(started_receiver.last_logger.related_objects, {user})

    @responses.activate
    def test_output_request_error_should_be_logged(self):
        expected_output_request_started_data = {
            'request_headers': {
                'User-Agent': 'python-requests/2.26.0',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Content-Length': '16'
            },
            'request_body': '{"test": "test"}',
            'method': 'POST',
            'host': 'test.cz',
            'path': '/test',
            'queries': {},
            'is_secure': True,
            'start': _all_,
        }
        expected_output_request_error_data = {
            **expected_output_request_started_data,
            'stop': _all_,
            'error_message': _all_
        }
        with set_signal_receiver(output_request_started, expected_output_request_started_data) as started_receiver:
            with set_signal_receiver(output_request_finished) as finish_receiver:
                with set_signal_receiver(output_request_error, expected_output_request_error_data) as error_receiver:
                    with assert_raises(ConnectionError):
                        requests.post(
                            'https://test.cz/test',
                            data=json.dumps({'test': 'test'}),
                        )
                    assert_equal(started_receiver.calls, 1)
                    assert_equal(finish_receiver.calls, 0)
                    assert_equal(error_receiver.calls, 1)

    @responses.activate
    def test_response_sensitive_data_body_in_json_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        with set_signal_receiver(output_request_started) as started_receiver:
            requests.post('http://test.cz', data=json.dumps({'password': 'secret-password'}))
            assert_in('"password": "[Filtered]"', started_receiver.last_logger.data['request_body'])
            assert_not_in('"password": "secret-password"', started_receiver.last_logger.data['request_body'])
            assert_in('"password": "secret-password"', responses.calls[0].request.body)
            assert_not_in('"password": "[Filtered]"', responses.calls[0].request.body)

    @responses.activate
    def test_response_sensitive_headers_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        with set_signal_receiver(output_request_started) as started_receiver:
            requests.post('http://test.cz', headers={'token': 'secret'})
            assert_equal(started_receiver.last_logger.data['request_headers']['token'], '[Filtered]')
            assert_equal(responses.calls[0].request.headers['token'], 'secret')

    @responses.activate
    def test_response_sensitive_params_data_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        with set_signal_receiver(output_request_finished) as started_receiver:
            requests.post('http://test.cz', params={'token': 'secret'})
            assert_equal(started_receiver.last_logger.data['queries']['token'], '[Filtered]')
            assert_equal(responses.calls[0].request.url, 'http://test.cz/?token=secret')

    @responses.activate
    def test_response_more_sensitive_params_data_should_be_hidden(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        with set_signal_receiver(output_request_started) as started_receiver:
            requests.post('http://test.cz', params={'token': ['secret', 'secret2']})
            assert_equal(started_receiver.last_logger.data['queries']['token'], ['[Filtered]', '[Filtered]'])
            assert_equal(responses.calls[0].request.url, 'http://test.cz/?token=secret&token=secret2')

    @responses.activate
    def test_response_sensitive_params_and_url_query_together_data_should_be_logged(self):
        responses.add(responses.POST, 'http://test.cz', body='test')
        with set_signal_receiver(output_request_started) as started_receiver:
            requests.post('http://test.cz?a=1&a=2', params={'b': '6', 'a': '3', 'c': ['5']})
            assert_equal(started_receiver.last_logger.data['queries'], {'b': '6', 'a': ['1', '2', '3'], 'c': '5'})

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'sql'})
    @data_consumer('create_user')
    def test_output_request_should_be_logged_in_sql_backend(self, user):
        responses.add(responses.POST, 'https://test.cz/test', body='test')
        requests.post(
            'https://test.cz/test',
            data=json.dumps({'test': 'test'}),
            slug='test',
            related_objects=[user]
        )
        assert_equal(SQLOutputRequestLog.objects.count(), 1)
        sql_output_request_log = SQLOutputRequestLog.objects.get()
        assert_equal_model_fields(
            sql_output_request_log,
            request_headers={
                'User-Agent': 'python-requests/2.26.0',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Content-Length': '16'
            },
            request_body='{"test": "test"}',
            method='POST',
            host='test.cz',
            path='/test',
            queries={},
            is_secure=True,
            slug='test',
            time=(sql_output_request_log.stop - sql_output_request_log.start).total_seconds(),
            extra_data={},
            error_message=None,
            response_code=200,
            response_headers={'Content-Type': 'text/plain'},
            response_body='test',
            state=RequestLogState.INFO,
        )
        assert_equal([rel_obj.object for rel_obj in sql_output_request_log.related_objects.all()], [user])

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @data_consumer('create_user')
    def test_output_request_should_be_logged_in_elasticsearch_backend(self, user):
        responses.add(responses.POST, 'https://test.cz/test', body='test')
        with set_signal_receiver(output_request_finished) as output_request_finished_receiver:
            requests.post(
                'https://test.cz/test',
                data=json.dumps({'test': 'test'}),
                slug='test',
                related_objects=[user]
            )
            elasticsearch_output_request_log = ElasticsearchOutputRequestLog.get(
                id=output_request_finished_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_output_request_log,
                request_headers='{"User-Agent": "python-requests/2.26.0", "Accept-Encoding": "gzip, deflate", '
                                '"Accept": "*/*", "Connection": "keep-alive", "Content-Length": "16"}',
                request_body='{"test": "test"}',
                method='POST',
                host='test.cz',
                path='/test',
                queries='{}',
                is_secure=True,
                slug='test',
                time=(elasticsearch_output_request_log.stop - elasticsearch_output_request_log.start).total_seconds(),
                extra_data=None,
                error_message=None,
                response_code=200,
                response_headers='{"Content-Type": "text/plain"}',
                response_body='test',
                state=RequestLogState.INFO,
            )
            assert_equal(
                [rel_obj for rel_obj in elasticsearch_output_request_log.related_objects],
                ['default|3|{}'.format(user.id)]
            )

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'logging'})
    @data_consumer('create_user')
    def test_output_request_should_be_logged_in_logging_backend(self, user):
        responses.add(responses.POST, 'https://test.cz/test', body='test')
        with set_signal_receiver(output_request_finished) as finished_receiver:
            with self.assertLogs('security.output_request', level='INFO') as cm:
                requests.post(
                    'https://test.cz/test',
                    data=json.dumps({'test': 'test'}),
                    slug='test',
                    related_objects=[user]
                )
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.output_request:'
                        f'Output request "{finished_receiver.last_logger.id}" '
                        f'to "test.cz" with path "/test" is started',
                        f'INFO:security.output_request:'
                        f'Output request "{finished_receiver.last_logger.id}" '
                        f'to "test.cz" with path "/test" is successfully finished'
                    ]
                )

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'sql'})
    def test_error_output_request_should_be_logged_in_sql_backend(self,):
        with assert_raises(ConnectionError):
            requests.post(
                'https://test.cz/test',
                data=json.dumps({'test': 'test'}),
                slug='test',
            )
        assert_equal(SQLOutputRequestLog.objects.count(), 1)
        sql_output_request_log = SQLOutputRequestLog.objects.get()
        assert_equal_model_fields(
            sql_output_request_log,
            request_headers={
                'User-Agent': 'python-requests/2.26.0',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Content-Length': '16'
            },
            request_body='{"test": "test"}',
            method='POST',
            host='test.cz',
            path='/test',
            queries={},
            is_secure=True,
            slug='test',
            time=(sql_output_request_log.stop - sql_output_request_log.start).total_seconds(),
            extra_data={},
            response_code=None,
            response_headers=None,
            response_body=None,
            state=RequestLogState.ERROR,
        )
        assert_is_not_none(sql_output_request_log.error_message)

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    def test_error_output_request_should_be_logged_in_elasticsearch_backend(self):
        with set_signal_receiver(output_request_started) as started_receiver:
            with assert_raises(ConnectionError):
                requests.post(
                    'https://test.cz/test',
                    data=json.dumps({'test': 'test'}),
                    slug='test',
                )
            elasticsearch_input_request_log = ElasticsearchOutputRequestLog.get(
                id=started_receiver.last_logger.id
            )
            assert_equal_model_fields(
                elasticsearch_input_request_log,
                request_headers='{"User-Agent": "python-requests/2.26.0", "Accept-Encoding": "gzip, deflate", '
                                '"Accept": "*/*", "Connection": "keep-alive", "Content-Length": "16"}',
                request_body='{"test": "test"}',
                method='POST',
                host='test.cz',
                path='/test',
                queries='{}',
                is_secure=True,
                slug='test',
                time=(elasticsearch_input_request_log.stop - elasticsearch_input_request_log.start).total_seconds(),
                extra_data=None,
                response_code=None,
                response_headers=None,
                response_body=None,
                state=RequestLogState.ERROR,
            )
            assert_is_not_none(elasticsearch_input_request_log.error_message)

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'logging'})
    def test_error_output_request_should_be_logged_in_logging_backend(self):
        with set_signal_receiver(output_request_started) as output_request_started_receiver:
            with self.assertLogs('security.output_request', level='INFO') as cm:
                with assert_raises(ConnectionError):
                    requests.post(
                        'https://test.cz/test',
                        data=json.dumps({'test': 'test'}),
                        slug='test',
                    )
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.output_request:'
                        f'Output request "{output_request_started_receiver.last_logger.id}" '
                        f'to "test.cz" with path "/test" is started',
                        f'ERROR:security.output_request:'
                        f'Output request "{output_request_started_receiver.last_logger.id}" '
                        f'to "test.cz" with path "/test" is raised exception'
                    ]
                )

    @responses.activate
    @data_consumer('create_user')
    def test_slug_and_related_data_should_be_send_to_output_request_logger(self, user):
        responses.add(responses.POST, 'https://test.cz/test', body='test')
        with log_with_data(related_objects=[user], slug='TEST'):
            with set_signal_receiver(output_request_started) as started_receiver:
                requests.post(
                    'https://test.cz/test',
                    data=json.dumps({'test': 'test'}),
                )
                assert_equal(started_receiver.last_logger.related_objects, {user})
                assert_equal(started_receiver.last_logger.slug, 'TEST')
