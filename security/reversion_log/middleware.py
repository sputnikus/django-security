from reversion import revisions as reversion

from security.middleware import MiddlewareMixin
from security.reversion_log.models import InputRequestRevision


class RevisionLogMiddleware(MiddlewareMixin):

    def process_request(self, request):
        def create_revision_request_log(revision):
            if getattr(request, '_logged_request', False):
                InputRequestRevision.objects.create(logged_request=request._logged_request, revision=revision)

        reversion.add_callback(create_revision_request_log)
