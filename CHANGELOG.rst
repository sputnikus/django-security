.. _changelog:

django-security-logger changelog
================================

1.2.0 - 10/20/2020
------------------

- purge migrations because of splitting log to the extra database
- used new version of generic m2m relation which uses relations without FK
- added multiple database router

1.0.6 - 02/06/2020
------------------

- Added DB index to celery log task name.
- Celery log `state` is field on model now (is not dynamically computed).
- Celery log `state` is set in `LoggedTask` with methods `on_start_task`, `on_success_task`, `on_failure_task` and `on_retry_task`.
- Command `set_staletasks_to_error_state was` replaced with `set_celery_task_log_state` command.
