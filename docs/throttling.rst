.. _throttling:

Throttling
==========

In terms of ``django-security-logger`` throttling is a process responsible for regulating the rate of incoming HTTP requests. There are many ways how to restrict number of requests that may depend on a concrete view. The simplest throttling is to restrict maximum number of request from one IP address per unit of time.


Default configuration
---------------------

Default throttling configuration is set with ``SECURITY_DEFAULT_THROTTLING_VALIDATORS_PATH``. The setting contains path to the file with throttling configuration. Default configuration is ``'security.default_validators'`` and the config file content is::

    from .throttling import PerRequestThrottlingValidator


    default_validators = (
        PerRequestThrottlingValidator(3600, 1000),  # 1000 per an hour
        PerRequestThrottlingValidator(60, 20),  # 20 per an minute
    )

Validators
----------

There are only three predefined throttling validators:

* ``security.throttling.PerRequestThrottlingValidator`` - init parameters are ``timeframe`` throttling timedelta in seconds, ``throttle_at`` number of request per one IP address per timeframe and error message.
* ``security.throttling.UnsuccessfulLoginThrottlingValidator`` - validator with same input parameters as previous validator but counts only unsuccessful login request.
* ``security.throttling.SuccessfulLoginThrottlingValidator`` - validator with same input parameters as previous validator but counts only requests from anonymous (not logged in) user.

Custom validator
^^^^^^^^^^^^^^^^

Creating custom validator is very simple, you only create class with validate method that receives request and if request must be regulated the method raises ``security.exception.ThrottlingException``::

    class CustomValidator:

        def validate(self, request):
          if should_regulate(request):
              raise  ThrottlingException('Your custom message')


Decorators
----------

Because throttling can be different per view, there are decorators for changing default validators for concrete view:

* ``security.decorators.throttling_exempt()`` - marks a view function as being exempt from the throttling protection.
* ``security.decorators.throttling_exempt_all()`` - marks a view class as being exempt from the throttling protection.
* ``security.decorators.throttling(*validators, keep_default=True)`` - add throttling validators for view function. You can remove default throttling validators with set ``keep_default`` to the ``False`` value.
* ``security.decorators.throttling_all(*validators, keep_default=True)`` - add throttling validators for view class. You can remove default throttling validators with set ``keep_default`` to the ``False`` value.

View
----

If ``security.exception.ThrottlingException`` is raised the specific error view is returned. You can change it with only overriding template named 429.html in your templates. With setting ``SECURITY_THROTTLING_FAILURE_VIEW`` you can change view function which default code is::

    from django.shortcuts import render
    from django.utils.encoding import force_text


    def throttling_failure_view(request, exception):
        response = render(request, '429.html', {'description': force_text(exception)})
        response.status_code = 429
        return response
