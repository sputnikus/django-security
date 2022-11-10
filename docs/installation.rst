.. _installation:

Installation
============

Using PIP
---------

You can install django-security-logger via pip:

.. code-block:: console

    $ pip install django-security-logger


Configuration
=============

After installation you must go through these steps:

Required Settings
-----------------

The following variables have to be added to or edited in the project's ``settings.py``:

For using the library you just add ``security`` to ``INSTALLED_APPS`` variable::

    INSTALLED_APPS = (
        ...
        'security',
        ...
    )

Next you muse select which logging backend you want to use and add it into ``INSTALLED_APPS`` variable::

    INSTALLED_APPS = (
        ...
        'security.backends.sql',  # log is stored into SQL DB with Django ORM
        'security.backends.elasticsearch',  # log is stored into Elasticsearch DB with Elasticsearch-DSL
        'security.backends.logging',  # standard python log
        ...
    )


Next you must add  ``security.middleware.LogMiddleware`` to list of middlewares, the middleware should be added after authentication middleware::

    MIDDLEWARE = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'security.middleware.LogMiddleware',
        ...
    )


SQL backend
-----------

For SQL backend if your database configuration uses atomic requests, it's highly recommended to use second non atomic connection to your database for security logs. Possible rollback will not remove logs.

Example::

    DATABASES = {
        'default': {
            'NAME': 'db_name',
            'USER': 'db_user',
            'PASSWORD': 'db_password',
            'HOST': 'postgres',
            'PORT': 5432,
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'ATOMIC_REQUESTS': True,
        },
        'log': {
            'NAME': 'db_name',
            'USER': 'db_user',
            'PASSWORD': 'db_password',
            'HOST': 'postgres',
            'PORT': 5432,
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'ATOMIC_REQUESTS': False,
            'TEST': {
                'MIRROR': 'default', # Test purposes
            },
        },
    }
    DATABASE_ROUTERS = ['security.backends.sql.db_router.MirrorSecurityLoggerRouter']  # DB router which defines connection for logs
    SECURITY_DB_NAME = 'log'


For test purposes you will need to configure both databases to be tested::

    from django.test.testcases import TestCase

    class YourTestCase(TestCase):
        databases = ('default', 'log')


The second solution is have second storage for logs in this case you will use ``MultipleDBSecurityLoggerRouter``::

    DATABASES = {
        'default': {
            'NAME': 'db_name',
            'USER': 'db_user',
            'PASSWORD': 'db_password',
            'HOST': 'postgres',
            'PORT': 5432,
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'ATOMIC_REQUESTS': True,
        },
        'log': {
            'NAME': 'log_db_name',
            'USER': 'log_db_user',
            'PASSWORD': 'log_db_password',
            'HOST': 'log_db_postgres',
            'PORT': 5432,
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'ATOMIC_REQUESTS': False,
        },
    }
    DATABASE_ROUTERS = ['security.backends.sql.dbr_router.MultipleDBSecurityLoggerRouter']  # DB router which defines connection for logs
    SECURITY_DB_NAME = 'log'


Elasticsearch backend
---------------------

Elasticsearch backend can be configured via ``SECURITY_ELASTICSEARCH_DATABASE`` variable::

    SECURITY_ELASTICSEARCH_DATABASE = {
        'host': 'localhost',
    }


For elasticsearch database initialization you must run ``./manage.py init_elasticsearch_log`` command.

Testing backend
---------------

For testing purposes you can use `'security.backends.testing'` and add it to the installed apps::

    INSTALLED_APPS = (
        ...
        'security.backends.testing',
        ...
    )

Your test you can surround with `security.backends.testing.capture_security_logs` decorator/context processor::

    def your_test():
       with capture_security_logs() as logged_data:
            ...
            assert_length_equal(logged_data.input_request, 1)
            assert_length_equal(logged_data.output_request, 1)
            assert_length_equal(logged_data.command, 1)
            assert_length_equal(logged_data.celery_task_invocation, 1)
            assert_length_equal(logged_data.celery_task_run, 1)

Readers
-------

Some ``elasticsearch``, ``sql`` and ``testing`` backends can be used as readers too. You can use these helpers to get data from it:

* ``security.backends.reader.get_count_input_requests(from_time, ip=None, path=None, view_slug=None, slug=None, method=None, exclude_log_id=None)`` - to get count input requests with input arguments
* ``security.backends.reader.get_logs_related_with_object(logger_name, related_object)`` - to get list of logs which are related with object


Setup
-----

.. attribute:: SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH

  Path to the file with configuration of throttling validators. Default value is ``'security.default_validators'``.

.. attribute:: SECURITY_THROTTLING_FAILURE_VIEW

  Path to the view that returns throttling failure. Default value is ``'security.views.throttling_failure_view'``.

.. attribute:: SECURITY_LOG_REQUEST_IGNORE_URL_PATHS

  Set of URL paths that are omitted from logging.

.. attribute:: SECURITY_LOG_REQUEST_IGNORE_IP

  Tuple of IP addresses that are omitted from logging.

.. attribute:: SECURITY_LOG_REQUEST_BODY_LENGTH

  Maximal length of logged request body. More chars than defined are truncated. Default value is ``1000``. If you set ``None`` value the request body will not be truncated.

.. attribute:: SECURITY_LOG_RESPONSE_BODY_LENGTH

  Maximal length of logged response body. More chars than defined are truncated. Default value is ``1000``. If you set ``None`` value the response body will not be truncated.

.. attribute:: SECURITY_LOG_RESPONSE_BODY_CONTENT_TYPES

  Tuple of content types which request/response body are logged for another content types body are removed. Default value is ``('application/json', 'application/xml', 'text/xml', 'text/csv', 'text/html', 'application/xhtml+xml')``.

.. attribute:: SECURITY_LOG_JSON_STRING_LENGTH

  If request/response body are in JSON format and body is longer than allowed the truncating is done with a smarter way. String JSON values longer than value of this setting are truncated. Default value is ``250``. If you set ``None`` value this method will not be used.

.. attribute:: SECURITY_COMMAND_LOG_EXCLUDED_COMMANDS

  Because logger supports Django command logging too this setting contains list of commands that are omitted from logging. Default value is ``('runserver', 'makemigrations', 'migrate', 'sqlmigrate', 'showmigrations', 'shell', 'shell_plus', 'test', 'help', 'reset_db', 'compilemessages', 'makemessages', 'dumpdata', 'loaddata')``.

.. attribute:: SECURITY_HIDE_SENSITIVE_DATA_PATTERNS

  Setting contains patterns for regex function that goes through body and headers and replaces sensitive data with defined replacement.

.. attribute:: SECURITY_HIDE_SENSITIVE_DATA

  If set to True enables replacing of sensitive data with defined replacement `SECURITY_HIDE_SENSITIVE_DATA_PATTERNS` inside body and headers. Default value is ``True``.

.. attribute:: SECURITY_SENSITIVE_DATA_REPLACEMENT

  Setting contains sensitive data replacement value. Default value is ``'[Filtered]'``.

.. attribute:: SECURITY_APPEND_SLASH

  Setting same as Django setting ``APPEND_SLASH``. Default value is ``True``.

.. attribute:: SECURITY_CELERY_STALE_TASK_TIME_LIMIT_MINUTES

  Default wait timeout to set not triggered task to the failed state. Default value is ``60``.

.. attribute:: SECURITY_LOG_OUTPUT_REQUESTS

  Enable logging of output requests via logging module. Default value is ``True``.

.. attribute:: SECURITY_AUTO_GENERATE_TASKS_FOR_DJANGO_COMMANDS

  List or set of Django commands which will be automatically transformed into celery tasks.

.. attribute:: SECURITY_LOG_DB_NAME

  Name of the database which security uses to log events.

.. attribute:: SECURITY_BACKENDS

  With this setting you can select which backends will be used to store logs. Default value is ``None`` which means all installed backends are used.

.. attribute:: SECURITY_ELASTICSEARCH_DATABASE

  Setting can be used to set Elasticsearch database configuration.

.. attribute:: SECURITY_ELASTICSEARCH_AUTO_REFRESH

  Every write to the Elasticsearch database will automatically call auto refresh.

.. attribute:: SECURITY_LOG_STRING_IO_FLUSH_TIMEOUT

  Timeout which set how often will be stored output stream to the log. Default value is ``5`` (s).

.. attribute:: SECURITY_LOG_STRING_OUTPUT_TRUNCATE_LENGTH

  Max length of log output string. Default value is ``10000``.

.. attribute:: SECURITY_LOG_STRING_OUTPUT_TRUNCATE_OFFSET

  Because too frequent string truncation can cause high CPU load, log string is truncated by more characters. This setting defines this value which is by default ``1000``.

