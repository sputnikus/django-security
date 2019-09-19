from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.functional import cached_property

from security.config import settings


# File system storages
class BackupFileSystemStorage(FileSystemStorage):

    @cached_property
    def base_location(self):
        if not settings.LOG_BACKUP_PATH:
            raise ImproperlyConfigured('SECURITY_LOG_BACKUP_PATH settings is not set')
        return settings.LOG_BACKUP_PATH
