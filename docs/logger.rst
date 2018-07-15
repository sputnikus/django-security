.. _logger:

Logger
======

Input requests
--------------

Input requests are logged automatically with ``security.middleware.LogMiddleware``. The middleware create ``security.models.InputLoggedRequest`` object before sending request to next middleware. Response data to the logged requests are completed in the end. You can found logged request in the Django request objects with that way ``request.input_logged_request``.

Decorators
^^^^^^^^^^

There are several decorators for views and generic views that can be used for view logging configuration:

* ``security.decorators.hide_request_body`` - decorator for view that removes request body from logged request
* ``security.decoratorshide_request_body_all`` - decorator for generic view class that removes request body from logged request
* ``security.decoratorslog_exempt`` - decorator for view that exclude all requests to this view from logging
* ``security.decoratorslog_exempt_all`` - decorator for generic view class that exclude all requests to this view from logging

Django-reversion
^^^^^^^^^^^^^^^^

If you have installed ``django-reversion`` it is possible to relate input logged requests with concrete object change. Firstly you must add extension to your ``INSTALLED_APPS`` setting::

    INSTALLED_APPS = (
        ...
        'security',
        'security.reversion_log',
        ...
    )

For older ``django-reversion`` you must add middleware ``security.reversion_log.middleware.RevisionLogMiddleware`` too::

    MIDDLEWARE = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'security.middleware.LogMiddleware',
        'security.reversion_log.middleware.RevisionLogMiddleware',
        ...
    )

Input logged requests and reversion revision objects are related via m2m model ``security.reversion_log.models.InputRequestRevision``


Output requests
---------------

Log output requests are little bit complicated and is related with way how output requests are performed. Security provides two ways how to log output requests:


requests
^^^^^^^^

First way is for logging simple HTTP requests with using ``requests`` library. You only must use without ``import requests`` use ``from security.transport import security_requests as requests``. There is same methods (get, post, put, ..) as in requests library. Every method has two extra optional parameters:

* ``slug`` - text slug that is stored with the logged request to tag concrete logged value.
* ``related_objects`` - list or tuple of related objects that will be related with output logged request.

suds
^^^^

For WS there are extension to the ``suds`` library. You must only use ``security.transport.security_suds.Client`` class without standard suds client or ``security.transport.security_suds.SecurityRequestsTransport`` with standard suds client object.
As init data of ``security.transport.security_suds.SecurityRequestsTransport`` you can send ``slug`` and ``related_objects``.
The ``security.transport.security_suds.Client`` has ``slug`` as initial parameter bug related objects must be added via ``add_related_objects(self, *related_objects)`` method.

Decorators
^^^^^^^^^^

``security.transport.transaction.log_output_request`` - because logged request are stored in models if you are using transaction on log is executed rollback with the same way as for other models. To solve this problem you can use this decorator before Django ``transaction.atomic`` decorator. The logs are stored on the end of the transaction (even with raised exception). Decorator can be nested, logs are saved only with the last decorator.


Sensitive data
--------------

Because some sensitive data inside requests and responses should not be stored (for example password, authorization token, etc.) ``django-security-logger`` uses regex to find these cases and replace these values with information about hidden value. Patterns are set with ``SECURITY_HIDE_SENSITIVE_DATA_PATTERNS`` which default setting is::

    SECURITY_HIDE_SENSITIVE_DATA_PATTERNS = {
        'BODY': (
            r'"password"\s*:\s*"((?:\\"|[^"])*)',
            r'<password>([^<]*)',
            r'password=([^&]*)',
            r'csrfmiddlewaretoken=([^&]*)',
        ),
        'HEADERS': (
            r'Authorization',
            r'X_Authorization',
            r'Cookie',
            r'.*token.*',
        ),
    }

Patterns are split to two groups ``BODY`` and ``HEADERS``.
The simplest part is ``HEADERS``. There value of header name find by regex (which is not case sensitive) is replaced with replacement.
``BODY`` is little bit complicated. If regex groups are found in the pattern only these groups are replaced with replacement if no groups are in pattern the whole pattern is replaced.

Commands log
------------

If you want to log commands you must only modify your ``mangage.py`` file::

    if __name__ == '__main__':
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

        # Used function for security to log commands
        from security.management import execute_from_command_line

        sys.path.append(os.path.join(PROJECT_DIR, 'libs'))

        execute_from_command_line(sys.argv)

If you can call command from code, you should use ``security.management.call_command`` instead of standard Django ``call_command`` function.
