from settings.celery import app as celery_app

from security.task import LoggedTask


@celery_app.task(
    base=LoggedTask,
    bind=True,
    name='sum_task')
def sum_task(self, a, b):
    return a + b


@celery_app.task(
    base=LoggedTask,
    bind=True,
    name='error_task',
    stale_time_limit=60 * 60)
def error_task(self):
    raise RuntimeError('error')


@celery_app.task(
    base=LoggedTask,
    bind=True,
    name='retry_task',
    autoretry_for=(RuntimeError,),
    default_retry_delays=(1 * 60, 5 * 60, 10 * 60, 30 * 60, 60 * 60))
def retry_task(self):
    if self.request.retries != 5:
        raise RuntimeError('error')


@celery_app.task(
    base=LoggedTask,
    bind=True,
    name='unique_task',
    unique=True)
def unique_task(self):
    return 'unique'
