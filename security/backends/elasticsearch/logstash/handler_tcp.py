from logging.handlers import SocketHandler

from .formatter import LogstashFormatter


class TCPLogstashHandler(SocketHandler):
    """
    Python logging handler for Logstash. Sends events over TCP.
    :param host: The host of the logstash server.
    :param port: The port of the logstash server (default 5959).
    """

    def __init__(self, host, port=5959):
        super().__init__(host, port)
        self.formatter = LogstashFormatter()

    def makePickle(self, record):
        return self.formatter.format(record)
