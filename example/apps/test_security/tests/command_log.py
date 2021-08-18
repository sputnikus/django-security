import responses

from django import get_version
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.test import override_settings

from germanium.decorators import data_consumer
from germanium.test_cases.client import ClientTestCase
from germanium.tools import (
    assert_equal, assert_false, assert_http_not_found, assert_http_ok, assert_http_redirect,
    assert_http_too_many_requests, assert_in, assert_is_none, assert_is_not_none, assert_not_in,
    assert_raises, assert_true, assert_equal_model_fields
)

from security.config import settings
from security.decorators import log_with_data
from security.enums import CommandState
from security.backends.sql.models import CommandLog as SQLCommandLog
from security.backends.elasticsearch.models import CommandLog as ElasticsearchCommandLog

from security.backends.signals import (
    command_started, command_error, command_finished, command_output_updated, output_request_finished
)

from .base import (
    BaseTestCaseMixin, _all_, TRUNCATION_CHAR, assert_equal_dict_data, set_signal_receiver, test_call_command,
    _not_none_
)


@override_settings(SECURITY_BACKENDS={})
class CommandLogTestCase(BaseTestCaseMixin, ClientTestCase):

    def test_command_should_be_logged(self):
        expected_command_started_data = {
            'name': 'test_command',
            'input': 'verbosity=0',
            'is_executed_from_command_line': False,
            'start': _all_,
        }
        expected_command_finished_data = {
            **expected_command_started_data,
            'stop': _all_,
        }
        with set_signal_receiver(command_started, expected_command_started_data) as started_receiver:
            with set_signal_receiver(command_finished, expected_command_finished_data) as finish_receiver:
                with set_signal_receiver(command_output_updated) as output_updated_receiver:
                    with set_signal_receiver(command_error) as error_receiver:
                        test_call_command('test_command', verbosity=0)
                        assert_equal(started_receiver.calls, 1)
                        assert_equal(finish_receiver.calls, 1)
                        assert_equal(output_updated_receiver.calls, 1)
                        assert_equal(error_receiver.calls, 0)
                        assert_equal(len(output_updated_receiver.last_logger.data['output'].split('\n')), 21)

    @override_settings(SECURITY_LOG_STING_IO_FLUSH_TIMEOUT=0)
    def test_command_log_string_io_flush_timeout_should_changed(self):
        with set_signal_receiver(command_output_updated) as output_updated_receiver:
            test_call_command('test_command')
            assert_equal(output_updated_receiver.calls, 21)

    def test_error_command_should_be_logged(self):
        expected_command_started_data = {
            'name': 'test_error_command',
            'input': '',
            'is_executed_from_command_line': False,
            'start': _all_,
        }
        expected_command_error_data = {
            **expected_command_started_data,
            'error_message': _not_none_,
            'stop': _all_,
        }
        with set_signal_receiver(command_started, expected_command_started_data) as started_receiver:
            with set_signal_receiver(command_finished) as finish_receiver:
                with set_signal_receiver(command_error, expected_command_error_data) as error_receiver:
                    with assert_raises(RuntimeError):
                        test_call_command('test_error_command')
                    assert_equal(started_receiver.calls, 1)
                    assert_equal(finish_receiver.calls, 0)
                    assert_equal(error_receiver.calls, 1)

    @responses.activate
    @data_consumer('create_user')
    def test_command_with_response_should_be_logged_with_parent_data(self, user):
        responses.add(responses.POST, 'http://test.cz/test', body='test')
        with log_with_data(related_objects=[user], slug='TEST', extra_data={'test', 'test'}):
            with set_signal_receiver(command_started) as command_started_receiver:
                with set_signal_receiver(output_request_finished) as output_request_finished_receiver:
                    test_call_command('test_command_with_response')
                    assert_equal(
                        output_request_finished_receiver.last_logger.parent_with_id,
                        command_started_receiver.last_logger
                    )
                    assert_equal(command_started_receiver.last_logger.slug, 'TEST')
                    assert_equal(command_started_receiver.last_logger.related_objects, {user})
                    assert_equal(command_started_receiver.last_logger.extra_data, {'test', 'test'})
                    assert_equal(output_request_finished_receiver.last_logger.slug, 'TEST')
                    assert_equal(output_request_finished_receiver.last_logger.related_objects, {user})
                    assert_equal(output_request_finished_receiver.last_logger.extra_data, {'test', 'test'})

    @override_settings(SECURITY_BACKENDS={'sql'})
    @data_consumer('create_user')
    def test_command_should_be_logged_in_sql_backend(self, user):
        with log_with_data(related_objects=[user]):
            test_call_command('test_command', verbosity=0)
            assert_equal(SQLCommandLog.objects.count(), 1)
            sql_command_log = SQLCommandLog.objects.get()
            assert_equal_model_fields(
                sql_command_log,
                name='test_command',
                input='verbosity=0',
                is_executed_from_command_line=False,
                time=(sql_command_log.stop - sql_command_log.start).total_seconds(),
                state=CommandState.SUCCEEDED,
                error_message=None,
            )
            assert_is_not_none(sql_command_log.output)
            assert_equal([rel_obj.object for rel_obj in sql_command_log.related_objects.all()], [user])

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @data_consumer('create_user')
    def test_command_should_be_logged_in_elasticsearch_backend(self, user):
        with set_signal_receiver(command_started) as started_receiver:
            with log_with_data(related_objects=[user]):
                test_call_command('test_command', verbosity=0)
                elasticsearch_command_log = ElasticsearchCommandLog.get(
                    id=started_receiver.last_logger.id
                )
                assert_equal_model_fields(
                    elasticsearch_command_log,
                    name='test_command',
                    input='verbosity=0',
                    is_executed_from_command_line=False,
                    time=(elasticsearch_command_log.stop - elasticsearch_command_log.start).total_seconds(),
                    state=CommandState.SUCCEEDED,
                    error_message=None,
                )
                assert_is_not_none(elasticsearch_command_log.output)
                assert_equal(
                    [rel_obj for rel_obj in elasticsearch_command_log.related_objects],
                    ['default|3|{}'.format(user.id)]
                )

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'logging'})
    @data_consumer('create_user')
    def test_command_should_be_logged_in_logging_backend(self, user):
        with set_signal_receiver(command_started) as finished_receiver:
            with self.assertLogs('security.command', level='INFO') as cm:
                test_call_command('test_command', verbosity=0)
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.command:'
                        f'Command "{finished_receiver.last_logger.id}" '
                        f'with name "test_command" is started',
                        f'INFO:security.command:'
                        f'Command "{finished_receiver.last_logger.id}" '
                        f'with name "test_command" is successfully finished',
                    ]
                )

    @override_settings(SECURITY_BACKENDS={'sql'})
    @data_consumer('create_user')
    def test_error_command_should_be_logged_in_sql_backend(self, user):
        with log_with_data(related_objects=[user]):
            with assert_raises(RuntimeError):
                test_call_command('test_error_command')
            assert_equal(SQLCommandLog.objects.count(), 1)
            sql_command_log = SQLCommandLog.objects.get()
            assert_equal_model_fields(
                sql_command_log,
                name='test_error_command',
                input='',
                is_executed_from_command_line=False,
                time=(sql_command_log.stop - sql_command_log.start).total_seconds(),
                state=CommandState.FAILED,
                output='',
            )
            assert_is_not_none(sql_command_log.error_message)
            assert_equal([rel_obj.object for rel_obj in sql_command_log.related_objects.all()], [user])

    @override_settings(SECURITY_BACKENDS={'elasticsearch'})
    @data_consumer('create_user')
    def test_error_command_should_be_logged_in_elasticsearch_backend(self, user):
        with set_signal_receiver(command_started) as started_receiver:
            with log_with_data(related_objects=[user]):
                with assert_raises(RuntimeError):
                    test_call_command('test_error_command')
                elasticsearch_command_log = ElasticsearchCommandLog.get(
                    id=started_receiver.last_logger.id
                )
                assert_equal_model_fields(
                    elasticsearch_command_log,
                    name='test_error_command',
                    input='',
                    is_executed_from_command_line=False,
                    time=(elasticsearch_command_log.stop - elasticsearch_command_log.start).total_seconds(),
                    state=CommandState.FAILED,
                    output='',
                )
                assert_is_not_none(elasticsearch_command_log.error_message)
                assert_equal(
                    [rel_obj for rel_obj in elasticsearch_command_log.related_objects],
                    ['default|3|{}'.format(user.id)]
                )

    @responses.activate
    @override_settings(SECURITY_BACKENDS={'logging'})
    @data_consumer('create_user')
    def test_error_command_should_be_logged_in_logging_backend(self, user):
        with set_signal_receiver(command_started) as finished_receiver:
            with self.assertLogs('security.command', level='INFO') as cm:
                with assert_raises(RuntimeError):
                    test_call_command('test_error_command')
                assert_equal(
                    cm.output,
                    [
                        f'INFO:security.command:'
                        f'Command "{finished_receiver.last_logger.id}" '
                        f'with name "test_error_command" is started',
                        f'ERROR:security.command:'
                        f'Command "{finished_receiver.last_logger.id}" '
                        f'with name "test_error_command" is finished with exception',
                    ]
                )

    def test_data_change_should_be_connected_with_command_log(self):
        with set_signal_receiver(command_finished) as finish_receiver:
            test_call_command('create_user')
            assert_equal(
                list(finish_receiver.last_logger.related_objects)[0].version_set.get().content_type,
                ContentType.objects.get_for_model(User)
            )

    @override_settings(SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS=('test_command',))
    def test_excluded_command_should_not_be_logged(self):
        with set_signal_receiver(command_started) as started_receiver:
            with set_signal_receiver(command_finished) as finish_receiver:
                with set_signal_receiver(command_output_updated) as output_updated_receiver:
                    with set_signal_receiver(command_error) as error_receiver:
                        test_call_command('test_command')
                        assert_equal(started_receiver.calls, 0)
                        assert_equal(finish_receiver.calls, 0)
                        assert_equal(output_updated_receiver.calls, 0)
                        assert_equal(error_receiver.calls, 0)
