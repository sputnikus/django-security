from django.contrib.auth import get_user_model
from django.db.models import TextField
from django.db.models.functions import Cast

from pyston.filters.django_filters import SimpleMethodEqualFilter
from pyston.filters.filters import OPERATORS


class UsernameUserFilter(SimpleMethodEqualFilter):

    allowed_operators = (OPERATORS.CONTAINS,)

    def clean_value(self, value, operator_slug, request):
        user_model = get_user_model()
        return list(
            user_model.objects.filter(
                **{'{}__contains'.format(user_model.USERNAME_FIELD): value}
            ).annotate(
                str_id=Cast('id', output_field=TextField())
            ).values_list('str_id', flat=True)
        )

    def get_filter_term(self, value, operator_slug, request):
        return {'user_id__in': value}
