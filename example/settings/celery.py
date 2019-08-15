import os
import sys

from celery import Celery

from django.conf import settings

app = Celery('example')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks()
