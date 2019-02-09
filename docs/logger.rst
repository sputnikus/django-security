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

Django-reversion
^^^^^^^^^^^^^^^^

If you have installed ``django-reversion`` it is possible to relate input logged requests with concrete object change. Firstly you must add extension to your ``INSTALLED_APPS`` setting::

    INSTALLED_APPS = (
        ...
        'security',
        'security.reversion_log',
        ...
    )

For ``django-reversion`` version older than 2.x you must add middleware ``security.reversion_log.middleware.RevisionLogMiddleware`` too::

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
