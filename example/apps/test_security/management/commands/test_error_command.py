from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def handle(self, **options):
        raise RuntimeError('error')
