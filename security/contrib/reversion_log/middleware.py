from reversion import revisions as reversion

from security.contrib.reversion_log.models import InputRequestRevision


class RevisionLogMiddleware:

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        def create_revision_request_log(revision):
            if getattr(request, 'input_logged_request', False):
                InputRequestRevision.objects.create(logged_request=request.input_logged_request, revision=revision)

        reversion.add_callback(create_revision_request_log)

        return self.get_response(request)
