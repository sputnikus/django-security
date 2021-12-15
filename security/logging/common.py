import copy

from threading import local
from attrdict import AttrDict

from uuid import uuid4

from contextlib import ContextDecorator

from django.conf import settings as django_settings

from security.config import settings


class SecurityLogger(ContextDecorator, local):

    loggers = []
    name = None
    store = True

    def __init__(self, id=None, related_objects=None, slug=None, data=None, extra_data=None):
        self.id = id or (uuid4() if self.name else None)
        self.parent = SecurityLogger.loggers[-1] if SecurityLogger.loggers else None
        self.related_objects = set(related_objects) if related_objects else set()
        self.slug = slug
        if self.parent:
            self.related_objects |= self.parent.related_objects
            if not self.slug:
                self.slug = self.parent.slug
        self.data = {}
        if data:
            self.data.update(data)
        self.parent_with_id = self._get_parent_with_id()
        self._extra_data = extra_data
        if self._extra_data is None:
            self._extra_data = self.parent.extra_data if self.parent else {}

        if self.store:
            SecurityLogger.loggers.append(self)

            if 'reversion' in django_settings.INSTALLED_APPS:
                from reversion.signals import post_revision_commit

                post_revision_commit.connect(self._post_revision_commit, weak=False)
        self.backend_logs = AttrDict()

    def _get_parent_with_id(self):
        parent = self.parent
        while parent and not parent.id:
            parent = parent.parent
        return parent

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.store:
            self.close()

    def set_slug(self, slug):
        self.slug = slug

    def add_related_objects(self, *related_objects):
        self.related_objects |= set(related_objects)

    @property
    def extra_data(self):
        return copy.deepcopy(self._extra_data)

    def update_extra_data(self, data):
        self._extra_data.update(data)

    def close(self):
        if not SecurityLogger.loggers or SecurityLogger.loggers[-1] != self:
            raise RuntimeError('Log already finished')

        SecurityLogger.loggers.pop()
        if 'reversion' in django_settings.INSTALLED_APPS:
            from reversion.signals import post_revision_commit

            post_revision_commit.disconnect(self._post_revision_commit)

    @property
    def release(self):
        return settings.RELEASE

    def _post_revision_commit(self, **kwargs):
        """
        Called as a post save of revision model of the reversion library.
        If log context manager is active input logged request, command
        log or celery task run log is joined with revision via related objects.
        """
        self.update_extra_data({
            'reversion': {
                'revision_id': kwargs['revision_id'] if 'revision_id' in kwargs else kwargs['revision'].id
            }
        })
