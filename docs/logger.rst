.. _logger:

Logger
======

Input requests
--------------

Input requests are logged automatically with ``security.middleware.LogMiddleware``. The middleware creates ``security.models.InputLoggedRequest`` object before sending request to next middleware. Response data to the logged requests are completed in the end. You can found logged request in the Django request objects with that way ``request.input_logged_request``.

Decorators
^^^^^^^^^^

There are several decorators for views and generic views that can be used for view logging configuration:

* ``security.decorators.hide_request_body`` - decorator for view that removes request body from logged request
* ``security.decorators.hide_request_body_all`` - decorator for generic view class that removes request body from logged request
* ``security.decorators.log_exempt`` - decorator for view that exclude all requests to this view from logging
* ``security.decorators.log_exempt_all`` - decorator for generic view class that exclude all requests to this view from logging


Output requests
---------------

Logging of output requests is a little bit complicated and is related to the way how output requests are performed. Security provides two ways how to log output requests:


requests
^^^^^^^^

The first method is used for logging simple HTTP requests using ``requests`` library. The only change necessary is to import ``from security.transport import security_requests as requests`` instead of ``import requests``. Same methods (get, post, put, ..) are available as in the requests library. Every method has two extra optional parameters:

* ``slug`` - text slug that is stored with the logged request to tag concrete logged value
* ``related_objects`` - list or tuple of related objects that will be related with output logged request

suds
^^^^

For SOAP based clients there are extensions to the ``suds`` library. You must only use ``security.transport.security_suds.Client`` class without standard suds client or ``security.transport.security_suds.SecurityRequestsTransport`` with standard suds client object.
As init data of ``security.transport.security_suds.SecurityRequestsTransport`` you can send ``slug`` and ``related_objects``.
The ``security.transport.security_suds.Client`` has ``slug`` as initial parameter bug related objects must be added via ``add_related_objects(self, *related_objects)`` method.

Decorators
^^^^^^^^^^

``security.transport.transaction.log_output_request`` - because logged requests are stored in models, they are subject to rollback, if you are using transactions. To solve this problem you can use this decorator before Django ``transaction.atomic`` decorator. The logs are stored on the end of the transaction (even with raised exception). Decorator can be nested, logs are saved only with the last decorator.


Sensitive data
--------------

Because some sensitive data inside requests and responses should not be stored (for example password, authorization token, etc.) ``django-security-logger`` uses regex to find these cases and replace these values with information about hidden value. Patterns are set with ``SECURITY_HIDE_SENSITIVE_DATA_PATTERNS`` which default setting is::

    SECURITY_HIDE_SENSITIVE_DATA_PATTERNS = {
        'BODY': (
            r'"password"\s*:\s*"((?:\\"|[^"])*)',
            r'<password>([^<]*)',
            r'password=([^&]*)',
            r'csrfmiddlewaretoken=([^&]*)',
            r'(?i)content-disposition: form-data; name="password"\r\n\r\n.*',
            r'"access_key": "([^"]*)',
        ),
        'HEADERS': (
            r'Authorization',
            r'X_Authorization',
            r'Cookie',
            r'.*token.*',
        ),
        'QUERIES': (
            r'.*token.*',
        ),
    }

Patterns are split to two groups ``BODY``, ``HEADERS`` and ``QUERIES``.
There are names of HTTP headers and queries, whose values will be replaced by the replacement. The search is case insensitive.
``BODY`` is a little bit complicated. If regex groups are used in the pattern only these groups will be replaced with the replacement. If no groups are used, the whole pattern will be replaced.

Commands log
------------

If you want to log commands you must only modify your ``mangage.py`` file::

    if __name__ == '__main__':
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

        # Used function for security to log commands
        from security.management import execute_from_command_line

        sys.path.append(os.path.join(PROJECT_DIR, 'libs'))

        execute_from_command_line(sys.argv)

If you want to call command from code, you should use ``security.management.call_command`` instead of standard Django ``call_command`` function.

Celery tasks log
----------------

If you want to log celery tasks you must firsly install celery library (celery==4.3.0). Then you must define your task as in example::

    from security.tasks import LoggedTask

    @celery_app.task(
        base=LoggedTask,
        bind=True,
        name='sum_task')
    def sum_task(self, task_id, a, b):
        return a + b

Task result will be automatically logged to the ``security.models.CeleryTaskLog``.

You can use predefined celery task ``security.tasks.call_django_command`` to run arbitrary django command. For example::

    from security.tasks import call_django_command

    call_django_command.apply_async(args=('check',))

.. class:: security.tasks.LoggedTask

  There are several methods of ``LoggedTask`` which you can use for your advanced tasks logic.

  .. property:: task_run_log

    This property returns an instance of CeleryTaskRunLog related to your task.

  .. method:: on_apply_task(task_log, args, kwargs, options)

    This method is called before the task is queued. You can override this method.

  .. method:: on_start_task(task_run_log, args, kwargs)

    This method is called when the task was started.

  .. method:: on_success_task(task_run_log, args, kwargs, retval)

    This method is called when the task was successfully completed.

  .. method:: on_failure_task(task_run_log, args, kwargs, exc)

    This method is called when the task raised an exception and is not retried.

  .. method:: on_retry_task(task_run_log, args, kwargs, exc)

    This method is called when the task raised an exception and is retried.

  .. method:: apply_async_on_commit(args=None, kwargs=None, **options)

    This method has the same behaviour as ``apply_async`` but runs task with ``on_commit`` django signal. Therefore it is initialized at the end of the django atomic block.

  .. method:: delay_on_commit(*args, **kwargs)

    This method is same as ``delay`` method only uses for task initialization ``apply_async_on_commit``.

  .. property:: default_retry_delays

    Similar to celery ``default_retry_delay`` which you can use to define how long the retried task will wait, property  ``default_retry_delays`` can be used to define the same but every task attempt may have a different delay::

        @celery_app.task(
            base=LoggedTask,
            bind=True,
            name='retry_task',
            autoretry_for=(RuntimeError,),
            default_retry_delays=(1 * 60, 5 * 60, 10 * 60, 30 * 60, 60 * 60))
        def retry_task(self):
            ...

    The ``retry_task`` will be retried after 1 minute for second attempt, 5 minutes for third attempt and so on.

  .. property:: stale_time_limit

    ``stale_time_limit`` is value in seconds which defines, how long it will take to set the task as expired. Default value can be set with ``CELERYD_TASK_STALE_TIME_LIMIT`` in Django settings.

  .. property:: retry_error_message

    Is the message which will be logged as warning if task is retried. Default value is ``'Task "{task_name}" ({task}) failed on exception: "{exception}", attempt: "{attempt}" and will be retried'``

  .. property:: fail_error_message

    Is the message which will be logged as warning if task is failed. Default value is ``'Task "{task_name}" ({task}) failed on exception: "{exception}"'``

  .. property:: unique

    LoggedTask can guarantee unique celery task. It means that only one task with the same name and input can run at one time. If task is already running its ``AsyncResult`` is returned in the methods ``apply_async``, ``apply_async_on_commit``, ``delay`` or ``LoggedTask`` can guarantee unique celery task.

  .. property:: unique_key_generator

    ``unique_key_generator`` is value which defines function that is used for task unique key computation. Default generator looks like::

        def default_unique_key_generator(task, task_args, task_kwargs):
            unique_key = [task.name]
            if task_args:
                unique_key += [str(v) for v in task_args]
            if task_kwargs:
                unique_key += ['{}={}'.format(k, v) for k, v in task_kwargs.items()]
            return '||'.join(unique_key)
