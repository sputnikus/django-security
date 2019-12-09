from is_core.generic_views.inlines.inline_form_views import TabularInlineFormView

from .models import InputRequestRevision


class RequestRevisionTabularInlineFormView(TabularInlineFormView):

    model = InputRequestRevision
