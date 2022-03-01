import logging
import socket
from datetime import datetime

from .serializer import serialize_message


class LogstashFormatter(logging.Formatter):

    def __init__(self):
        self._host = socket.gethostname()

    @classmethod
    def format_timestamp(cls, time):
        tstamp = datetime.utcfromtimestamp(time)
        return tstamp.strftime("%Y-%m-%dT%H:%M:%S") + ".%03d" % (tstamp.microsecond / 1000) + "Z"

    def format(self, record):
        return serialize_message(record.getMessage(), {
            'logger': {
                'host': self._host,
                'path': record.pathname,
                'timestamp': self.format_timestamp(record.created),
                'level': record.levelname,
                'logger_name': record.name,
            },
            **getattr(record, 'metadata', {}),
        })
