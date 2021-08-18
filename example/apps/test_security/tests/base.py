from io import StringIO

from contextlib import contextmanager

from django.contrib.auth.models import User

from germanium.decorators import data_provider
from germanium.tools import assert_equal, assert_false, assert_is_not_none

from security.management import call_command


TRUNCATION_CHAR = '…'


class BaseTestCaseMixin:

    databases = ['default', 'security']

    @data_provider
    def create_user(self, username='test', email='test@test.cz'):
        return User.objects._create_user(username, email, 'test', is_staff=True, is_superuser=True)


_all_ = object()
_not_none_ = object()


def assert_equal_dict_data(data, expected_data):
    if expected_data is _all_:
        return True
    else:
        assert_false(set(data.keys()) - set(expected_data.keys()), 'Extra keys {}'.format(','.join(
            set(data.keys()) - set(expected_data.keys()
        ))))
        assert_false(set(expected_data.keys()) - set(data.keys()), 'Missing keys {}'.format(','.join(
            set(expected_data.keys()) - set(data.keys()
        ))))
        for k, v in data.items():
            if expected_data[k] is _all_:
                pass
            elif expected_data[k] is _not_none_:
                assert_is_not_none(v, f'Invalid data with key {k} value should not be None')
            elif isinstance(v, dict):
                assert_equal_dict_data(v, expected_data[k])
            else:
                assert_equal(v, expected_data[k], f'Invalid data with key {k} {v}!={expected_data[k]}')


@contextmanager
def set_signal_receiver(signal, expected_data=None):
    def signal_receiver(sender, logger, **kwargs):
        if expected_data:
            assert_equal_dict_data(logger.data, expected_data)
        signal_receiver.loggers.append(logger)
        signal_receiver.last_logger = logger
        signal_receiver.calls += 1
    signal_receiver.calls = 0
    signal_receiver.loggers = []
    signal_receiver.last_logger = None
    try:
        signal.connect(signal_receiver)
        yield signal_receiver
    finally:
        signal.disconnect(signal_receiver)


def test_call_command(*args, **kwargs):
    call_command(*args, **kwargs, stdout=StringIO(), stderr=StringIO())
