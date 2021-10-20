.. _commands:

Commands
========

purge_logs
---------

Remove old request, command or celery logs that are older than defined value, parameters:

* ``expiration`` - timedelta from which logs will be removed. Units are h - hours, d - days, w - weeks, m - months, y - years
* ``noinput`` - tells Django to NOT prompt the user for input of any kind
* ``backup`` - tells Django where to backup removed logs in JSON format
* ``type`` - tells Django what type of requests should be removed (input-request/output-request/command/celery)

set_celery_task_log_state
-------------------------

Set celery tasks which are in WAITING state. Tasks which were not started more than ``SECURITY_CELERY_STALE_TASK_TIME_LIMIT_MINUTES`` (by default 60 minutes) to the failed state. Task with succeeded/failed task run is set to succeeded/failed state.

run_celery
---------

Run celery worker or beater with autoreload, parameters:

* ``type`` - type of the startup (beat or worker)
* ``celerysettings`` - path to the celery configuration file
* ``autoreload`` - tells Django to use the auto-reloader
* ``extra`` - extra celery startup arguments

celery_health_check
-------------------

Check Celery queue health. Either by count of tasks with state ``WAITING`` (``--max-tasks-count``) or by time waiting in queue (``--max-created-at-diff``, in seconds) or both at once. Default queue name is ``default``. You can change queue name with argument ``--queue-name``.
