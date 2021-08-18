from django.conf import settings

from .exception import ThrottlingException


class ThrottlingValidator:

    def __init__(self, timeframe, throttle_at, description):
        self.timeframe = timeframe
        self.throttle_at = throttle_at
        self.description = description

    def validate(self, request):
        if not getattr(settings, 'TURN_OFF_THROTTLING', False) and not self._validate(request):
            raise ThrottlingException(self.description)

    def _validate(self, request):
        raise NotImplemented

    def __repr__(self):
        return '<{} (timeframe={}, throttle_at={}, description={})>'.format(
            self.__class__.__name__, self.timeframe, self.throttle_at, self.description
        )
