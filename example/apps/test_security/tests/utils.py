import datetime
import uuid
import decimal

from django.utils.timezone import now

from germanium.test_cases.default import GermaniumTestCase
from germanium.tools import assert_equal
from germanium.decorators import data_consumer

from freezegun import freeze_time

from django.test import override_settings

from security.utils import serialize_data, deserialize_data, truncate_lines_from_left, LogStringIO


class UtilsTestCase(GermaniumTestCase):

    def test_utils_serialize_and_deserialize_data_should_return_right_values(self):
        data = {
            'a': datetime.datetime(2018, 1, 10, 5, 47, 11),
            'b': [datetime.date(2020, 5, 21), datetime.time(16, 59)],
            'c': {
                'd': uuid.UUID('06335e84-2872-4914-8c5d-3ed07d2a2f16'),
                'e': decimal.Decimal('158.687')
            },
            'f': datetime.timedelta(days=4, hours=15, minutes=6, seconds=45),
            'g': [5, 'test'],
        }
        serialized_data = {
            'a': {'@type': 'datetime', '@value': '2018-01-10T05:47:11'},
            'b': [{'@type': 'date', '@value': '2020-05-21'}, {'@type': 'time', '@value': '16:59:00'}],
            'c': {
                'd': {'@type': 'uuid', '@value': '06335e84-2872-4914-8c5d-3ed07d2a2f16'},
                'e': {'@type': 'decimal', '@value': '158.687'}
            },
            'f': {'@type': 'timedelta', '@value': 'P4DT15H06M45S'},
            'g': [5, 'test']
        }
        assert_equal(serialize_data(data), serialized_data)
        assert_equal(deserialize_data(serialized_data), data)

    @data_consumer(
        (
            ('test', 'test', 10),
            ('long truncated value without newline', '…\n', 10),
            ('long truncated value with\nnewline', '…\nnewline', 10),
            ('long truncated value with\nnewline', '…\n', 5),
            ('long truncated value with newline after end \n', '…\n', 5)
        )
    )
    def test_truncate_lines_from_left_should_truncate_text(self, original_text, truncated_text, length):
        assert_equal(truncate_lines_from_left(original_text, length), truncated_text)

    @override_settings(
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_LENGTH=100,
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_OFFSET=10
    )
    def test_log_string_io_should_be_truncated_according_to_settings(self):
        log_string_io = LogStringIO(write_time=False)
        for _ in range(20):
            log_string_io.write((4*'a') + '\n')
        assert_equal(log_string_io.getvalue(), 20*(4*'a' + '\n'))
        assert_equal(len(log_string_io.getvalue()), 100)
        log_string_io.write('b')
        assert_equal(log_string_io.getvalue(), '…\n' + 17*(4*'a' + '\n') + 'b')

    @override_settings(
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_LENGTH=100,
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_OFFSET=10
    )
    def test_log_string_io_should_remove_line_with_cr_lf(self):
        log_string_io = LogStringIO(write_time=False)
        log_string_io.write('text before newline\n')
        log_string_io.write('removed text')
        assert_equal(log_string_io.getvalue(), 'text before newline\nremoved text')
        log_string_io.write('\rnew text')
        assert_equal(log_string_io.getvalue(), 'text before newline\nnew text')

    @override_settings(
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_LENGTH=100,
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_OFFSET=10
    )
    def test_log_string_io_should_truncate_and_remove_last_line(self):
        log_string_io = LogStringIO(write_time=False)
        log_string_io.write('very long text which should be removed\n')
        log_string_io.write('very long text which shouldn\'t be removed\n')
        assert_equal(
            log_string_io.getvalue(),
            'very long text which should be removed\n'
            'very long text which shouldn\'t be removed\n'
        )
        log_string_io.write('text which should be removed with cr lf')
        assert_equal(
            log_string_io.getvalue(),
            '…\n'
            'very long text which shouldn\'t be removed\n'
            'text which should be removed with cr lf'
        )

        log_string_io.write('\rnew text')
        assert_equal(
            log_string_io.getvalue(),
            '…\n'
            'very long text which shouldn\'t be removed\n'
            'new text'
        )

        log_string_io.write('\rnew very long text which should remove prev text' + 9*' ')
        assert_equal(
            log_string_io.getvalue(),
            '…\n'
            'new very long text which should remove prev text' + 9*' '
        )

        log_string_io.write('\rnew very long text which should be removed at all' + 50*' ')
        assert_equal(
            log_string_io.getvalue(),
            '…\n'
        )

    @freeze_time(now())
    def test_log_string_io_should_add_time_and_log_to_output(self):
        time_string = f'\x1b[0m\x1b[1m[{{}}] [{now().strftime("%d-%m-%Y %H:%M:%S")}]\x1b[0m '

        log_string_io = LogStringIO()
        log_string_io.write('test')
        assert_equal(log_string_io.getvalue(), time_string.format(1) + 'test')

        log_string_io.write(' test')
        assert_equal(log_string_io.getvalue(), time_string.format(1) + 'test test')

        log_string_io.write('\ntest')
        assert_equal(
            log_string_io.getvalue(),
            time_string.format(1) + 'test test\n'
            + time_string.format(2) + 'test'
        )

    @override_settings(
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_LENGTH=110,
        SECURITY_LOG_STRING_OUTPUT_TRUNCATE_OFFSET=10
    )
    @freeze_time(now())
    def test_log_string_io_should_add_time_and_log_to_output_but_remove_with_cr_lf(self):
        time_string = f'\x1b[0m\x1b[1m[{{}}] [{now().strftime("%d-%m-%Y %H:%M:%S")}]\x1b[0m '

        log_string_io = LogStringIO()
        log_string_io.write('long text that should be removed \n')
        assert_equal(
            log_string_io.getvalue(),
            time_string.format(1) + 'long text that should be removed \n' + time_string.format(2)
        )

        log_string_io.write('new text')
        assert_equal(
            log_string_io.getvalue(),
            '…\n'
            + time_string.format(2) + 'new text'
        )

        log_string_io.write('write very long text' + 100*' ')
        assert_equal(
            log_string_io.getvalue(),
            '…\n' + time_string.format(2)
        )

        log_string_io.write('new text')
        assert_equal(
            log_string_io.getvalue(),
            '…\n' + time_string.format(2) + 'new text'
        )
