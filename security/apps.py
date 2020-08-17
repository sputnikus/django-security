from django.apps import AppConfig
from django.db.models.signals import pre_migrate, post_migrate

from django_celery_extensions.config import DEFAULTS

from . import utils

# Patch django_celery_extensions configuration
DEFAULTS['AUTO_GENERATE_TASKS_BASE'] = 'security.task.LoggedTask'

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
