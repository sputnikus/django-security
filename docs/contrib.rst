Extra
=====

Django-security-logger provides extra features to improve your logged data.

security.contrib.reversion_log
------------------------------

If you have installed ``django-reversion`` it is possible to relate input logged requests with concrete object change. Firstly you must add extension to your ``INSTALLED_APPS`` setting::


    INSTALLED_APPS = (
        ...
        'security.contrib.reversion_log',
        ...
    )


For ``django-reversion`` version older than 2.x you must add middleware ``security.contrib.reversion_log.middleware.RevisionLogMiddleware`` too::

    MIDDLEWARE = (
        ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'security.middleware.LogMiddleware',
        'security.contrib.reversion_log.middleware.RevisionLogMiddleware',
        ...
    )

Input logged requests and reversion revision objects are related via m2m model ``security.contrib.reversion_log.models.InputRequestRevision``


security.contrib.debug_toolbar_log
----------------------------------

If you are using ``django-debug-toolbar`` you can log toolbar results with logged request. You only add extension to your ``INSTALLED_APPS`` setting::

    INSTALLED_APPS = (
        ...
        'security.contrib.reversion_log',
        ...
    )

And add  ``security.contrib.debug_toolbar_log.middleware.DebugToolbarLogMiddleware`` on the first place::

    MIDDLEWARE = (
        'security.contrib.debug_toolbar_log.middleware.DebugToolbarLogMiddleware',
        ...
    )

Finally you can start log debug toolbar settings with your logged requests by turning on settings::

    SECURITY_DEBUG_TOOLBAR = True

Do not forget turn on django DEBUG.

To show results in ``django-is-core`` you must set setting::

    SECURITY_SHOW_DEBUG_TOOLBAR = True
