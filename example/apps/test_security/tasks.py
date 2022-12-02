from datetime import timedelta

from settings.celery import app as celery_app

from security.task import LoggedTask


@celery_app.task(
    base=LoggedTask,
    name='sum_task')
def sum_task(a, b):
    return a + b


@celery_app.task(
    base=LoggedTask,
    name='error_task',
    stale_time_limit=60 * 60)
def error_task():
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
    name='unique_task',
    unique=True)
def unique_task():
    return 'unique'


@celery_app.task(
    base=LoggedTask,
    name='ignored_after_success_task',
    ignore_task_after_success=True,
    ignore_task_timedelta=timedelta(hours=1, minutes=5))
def ignored_after_success_task():
    return 'ignored_task_after_success'


@celery_app.task(
    base=LoggedTask,
    name='acks_late_with_no_failure_or_timeout_acknowledgement',
    acks_late=True,
    acks_on_failure_or_timeout=False)
def acks_late_with_no_failure_or_timeout_acknowledgement():
    raise RuntimeError('error')
