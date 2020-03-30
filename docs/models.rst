.. _models:

Models
======

.. class:: security.models.InputLoggedRequest

  Model for storing log of input logged requests

  .. attribute:: host

    ``CharField``, contains host of logged request.

  .. attribute:: method

    ``CharField``, HTTP method of logged request.

  .. attribute:: path

    ``CharField``, URL path of logged request.

  .. attribute:: queries

    ``JSONField``, HTTP query dictionary.

  .. attribute:: is_secure

    ``BooleanField``, contains ``True`` if was used HTTPS.

  .. attribute:: slug

    ``SlugField``, slug where is stored view name.

  .. attribute:: request_timestamp

    ``DateTimeField``, date and time when request was received.

  .. attribute:: request_headers

    ``JSONField`` request headers in dictionary format.

  .. attribute:: request_body

    ``TextField``, HTTP request body.

  .. attribute:: response_timestamp

    ``DateTimeField``, date and time when response was sent.

  .. attribute:: response_code

    ``PositiveSmallIntegerField``, response HTTP status code.

  .. attribute:: response_headers

    ``JSONField`` response headers in dictionary format.

  .. attribute:: response_body

    ``TextField``, HTTP response body.

  .. attribute:: status

    ``PositiveSmallIntegerField``, status of request in choices (incomplete, info, warning, error, debug, critical).

  .. attribute:: error_description

    ``TextField``, value contains traceback of exception that was raised during request.

  .. attribute:: exception_name

    ``CharField``, value contains name of the exception that was raised during request.

  .. attribute:: user

    ``ForeignKey``, foreign key to the logged user.

  .. attribute:: ip

    ``GenericIPAddressField``, IP address of the client.

  .. attribute:: type

    ``PositiveSmallIntegerField``, type of the request (common, throttled, successful login, unsuccessful login)



.. class:: security.models.OutputLoggedRequest

  Model for storing log of output logged requests

    .. attribute:: host

    ``CharField``, contains host of logged request.

  .. attribute:: method

    ``CharField``, HTTP method of logged request.

  .. attribute:: path

    ``CharField``, URL path of logged request.

  .. attribute:: queries

    ``JSONField``, HTTP query dictionary.

  .. attribute:: is_secure

    ``BooleanField``, contains ``True`` if was used HTTPS.

  .. attribute:: slug

    ``SlugField``, slug where is stored view name.

  .. attribute:: request_timestamp

    ``DateTimeField``, date and time when request was received.

  .. attribute:: request_headers

    ``JSONField`` request headers in dictionary format.

  .. attribute:: request_body

    ``TextField``, HTTP request body.

  .. attribute:: response_timestamp

    ``DateTimeField``, date and time when response was sent.

  .. attribute:: response_code

    ``PositiveSmallIntegerField``, response HTTP status code.

  .. attribute:: response_headers

    ``JSONField`` response headers in dictionary format.

  .. attribute:: response_body

    ``TextField``, HTTP response body.

  .. attribute:: status

    ``PositiveSmallIntegerField``, status of request in choices (incomplete, info, warning, error, debug, critical).

  .. attribute:: error_description

    ``TextField``, value contains traceback of exception that was raised during request.

  .. attribute:: exception_name

    ``CharField``, value contains name of the exception that was raised during request.

  .. attribute:: input_logged_request

    ``ForeignKey``, foreign key to the input request during which was output request performed.


.. class:: security.models.OutputLoggedRequestRelatedObjects

  You can relate a model objects with output logged request.

  .. attribute:: output_logged_request

    Relation to the output logged request.

  .. attribute:: command_log

    Relation to the command log.

  .. attribute:: celery_task_run_log

    Relation to the celery task run log.

  .. attribute:: content_type

    Content type of the related object.

  .. attribute:: object_id

    Identifier of the related object.

  .. attribute:: content_object

    Related object (``GenericForeignKey``)


.. class:: security.models.CommandLog

  Represents a log of a command run.

  .. attribute:: start

    Date and time when command was started.

  .. attribute:: stop

    Date and time when command finished.

  .. attribute:: name

    Name of the command.

  .. attribute:: input

    Arguments/options the command was run with.

  .. attribute:: executed_from_command_line

    Flag that indicates if command was run from the command line.

  .. attribute:: output

    Standard and error output of the command.

  .. attribute:: is_successful

    Flag that indicates if command finished successfully.

.. class:: security.models.CeleryTaskLog

  Represents a log of a celery task initiation.

  .. attribute:: celery_task_id

    Identifier of celery task. Computed as random uuid value.

  .. attribute:: name

    Name of the task.

  .. attribute:: queue_name

    Name of the task queue.

  .. attribute:: input

    Input args and kwargs of the celery task.

  .. attribute:: task_args

    List of task args which was serialized into JSONField.

  .. attribute:: task_kwargs

    Dict of task kwargs which was serialized into JSONField.

  .. attribute:: estimated_time_of_first_arrival

    Celery task estimated time of first arrival. Which was computed from celery task etc or countdown value.

  .. attribute:: expires

    Time of a task expiration. Waiting task will not be run if the time is a thing of the past.

  .. attribute:: stale

    Time when a task will be marked as stale and will be automatically set as expired.

  .. attribute:: is_set_as_stale

    Boolean value that identifies if task is expired.

  .. method:: get_start

    Date and time when task was started.

  .. method:: get_stop

    Date and time when task finished.

  .. method:: get_state

    State of the task (WAITING, ACTIVE, SUCCEEDED, FAILED, RETRIED, EXPIRED).


.. class:: security.models.CeleryTaskRunLog

  Represents a log of celery task run.

  .. attribute:: celery_task_id

    Identifier of celery task. Computed as random uuid value. There can be more logs with the same task number. But with the different retries value (retried tasks have same celery task ID).

  .. attribute:: start

    Date and time when task run was started.

  .. attribute:: stop

    Date and time when task run finished.

  .. attribute:: name

    Name of the task run.

  .. attribute:: state

    State of the task run (ACTIVE, SUCCEEDED, FAILED, RETRIED).

  .. attribute:: error_message

    Exception message when task fails.

  .. attribute:: queue_name

    Name of the task queue.

  .. attribute:: input

    Input args and kwargs of the celery task.

  .. attribute:: output

    Standard and error output of the celery task.

  .. attribute:: task_args

    List of task args which was serialized into JSONField.

  .. attribute:: task_kwargs

    Dict of task kwargs which was serialized into JSONField.

  .. attribute:: retries

    Task attempt number is the task was retried.

  .. attribute:: estimated_time_of_next_retry

    Celery task estimated time of arrival of retried task. Which was computed from celery task etc or countdown value.

