import reversion

from security.reversion_log.models import RequestRevision


class RevisionLogMiddleware(object):

    def process_request(self, request):
        def create_revision_request_log(revision):
            if request._logged_request:
                RequestRevision.objects.create(logged_request=request._logged_request, revision=revision)

        reversion.add_callback(create_revision_request_log)
