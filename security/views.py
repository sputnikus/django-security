from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils.encoding import force_text


def throttling_failure_view(request, exception):
    response = render_to_response('429.html', {'description': force_text(exception)},
                                  context_instance=RequestContext(request))
    response.status_code = 429
    return response
