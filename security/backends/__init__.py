from security.config import settings

LOG_DB_BACKENDS = ['security_backends_sql', 'security_backends_elasticsearch']


def is_processing_celery_task(task_name, related_objects=None):
    from django.apps import apps

    is_processing_celery_task = None

    for log_db_backend in LOG_DB_BACKENDS:
        app_config = apps.get_app_config(log_db_backend)
        if app_config.backend_name in settings.BACKENDS:
            try:
                is_processing_celery_task = bool(is_processing_celery_task) | (
                    app_config.models_module.is_processing_celery_task(
                        task_name, related_objects
                    )
                )
            except LookupError:
                pass

    if is_processing_celery_task is None:
        raise LookupError('No log DB backend was found')

    return is_processing_celery_task
