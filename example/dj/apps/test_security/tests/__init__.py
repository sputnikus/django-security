from django.test import LiveServerTestCase

from security.models import InputLoggedRequest

from germanium.tools import assert_equal


class SecurityTestCase(LiveServerTestCase):

    def test_every_request_should_be_logged(self):
        assert_equal(InputLoggedRequest.objects.count(), 0)
        self.client.get('/')
        assert_equal(InputLoggedRequest.objects.count(), 1)
