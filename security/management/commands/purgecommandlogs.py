from security.models import CommandLog
from security.utils import PurgeLogsBaseCommand


class Command(PurgeLogsBaseCommand):

    timestamp_field = 'start'
    model = CommandLog
