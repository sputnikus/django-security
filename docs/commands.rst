.. _commands:

Commands
========

purgelogs
---------

Remove old request, command or celery logs that are older than defined value, parameters:

* ``expiration`` - timedelta from which logs will be removed. Units are h - hours, d - days, w - weeks, m - months, y - years
* ``noinput`` - tells Django to NOT prompt the user for input of any kind
* ``backup`` - tells Django where to backup removed logs in JSON format
* ``type`` - tells Django what type of requests should be removed (input-request/output-request/command/celery)

setstaletaskstoerrorstate
-------------------------

Set tasks which is in WAITING state and was not started more thane ``SECURITY_CELERY_STALE_TASK_TIME_LIMIT_MINUTES`` (by default 60 minutes) to the failed state.

runcelery
---------

Run celery worker or beater with autoreload, parameters:

* ``type`` - type of the startup (beat or worker)
* ``celerysettings`` - path to the celery configuration file
* ``autoreload`` - tells Django to use the auto-reloader
* ``extra`` - extra celery startup arguments
