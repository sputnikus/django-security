from django.db.models.signals import pre_migrate, post_migrate

from security.config import settings


class MultipleDBSecurityLoggerRouter:
    """
    A router controlling that all read and write database operations for apps specified in route_app_labels
    will be performed via mirror without atomic.
    """

    route_app_labels = [
        'security',
    ]

    def _db_for_read_or_write(self, model):
        if model._meta.app_label in self.route_app_labels:
            return settings.LOG_DB_NAME
        return None

    def db_for_read(self, model, **hints):
        return self._db_for_read_or_write(model)

    def db_for_write(self, model, **hints):
        return self._db_for_read_or_write(model)

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == settings.LOG_DB_NAME
        else:
            return db != settings.LOG_DB_NAME
