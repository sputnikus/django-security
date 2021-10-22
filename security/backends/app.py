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
            self.reader_inst = import_module(f'{self.name}.reader').BackendReader()
            SecurityBackend.registered_readers[self.backend_name] = self.reader_inst
        if self.writer:
            self.writer_inst = import_module(f'{self.name}.writer').BackendWriter(self.backend_name)
            SecurityBackend.registered_writers[self.backend_name] = self.writer_inst
