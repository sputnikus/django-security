import sys

from django.db.models.signals import pre_migrate, post_migrate

from . import utils
from .config import settings


class MirrorSecurityLoggerRouter:
    """
    A router controlling tha all that read and write database operations will be performed via mirror without atomic.
    """

    route_app_labels = [
        'security', 'debug_toolbar_log'
    ]

    def _db_for_read_or_write(self, model):
        if not utils.is_running_migration and model._meta.app_label in self.route_app_labels:
            return settings.LOG_DB_NAME
        return None

    def db_for_read(self, model, **hints):
        return self._db_for_read_or_write(model)

    def db_for_write(self, model, **hints):
        return self._db_for_read_or_write(model)

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
