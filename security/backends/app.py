from importlib import import_module

from django.apps import AppConfig


class SecurityBackend(AppConfig):

    backend_name = None
    writer = True
    reader = False
    registered_writers = {}
    registered_readers = {}

    def ready(self):
        if self.reader:
            SecurityBackend.registered_readers[self.backend_name] = self
        if self.writer:
            from security.backends.signals import get_backend_receiver

            SecurityBackend.registered_writers[self.backend_name] = self
            import_module(f'{self.name}.writer').set_writer(get_backend_receiver(self.backend_name))

