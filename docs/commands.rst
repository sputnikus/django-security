.. _commands:

Commands
========

purgecommandlogs
----------------

Remove old commands logs that are older than defined value, parameters:

* ``expiration`` - timedelta from which logs will be removed. Units are h - hours, d - days, w - weeks, m - months, y - years
* ``noinput`` - tells Django to NOT prompt the user for input of any kind
* ``backup`` - tells Django where to backup removed logs in JSON format

purgeloggedrequests
-------------------

Remove old requests logs that are older than defined value, parameters:

* ``expiration`` - timedelta from which logs will be removed. Units are h - hours, d - days, w - weeks, m - months, y - years
* ``noinput`` - tells Django to NOT prompt the user for input of any kind
* ``backup`` - tells Django where to backup removed logs in JSON format
* ``type`` - tells Django what type of requests should be removed (input/output)


