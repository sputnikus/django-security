from django.apps import AppConfig
from django.db.models.signals import pre_migrate, post_migrate

from . import utils


def start_migration(sender, **kwargs):
    utils.is_running_migration = True


def end_migration(sender, **kwargs):
    utils.is_running_migration = False


class SecurityLoggerAppConfig(AppConfig):

    name = 'security'
    verbose_name = 'Security'

    def ready(self):
        pre_migrate.connect(start_migration, sender=self)
        post_migrate.connect(end_migration, sender=self)
