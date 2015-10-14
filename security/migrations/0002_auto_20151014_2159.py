# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loggedrequest',
            name='request_timestamp',
            field=models.DateTimeField(verbose_name='Request timestamp', db_index=True),
        ),
    ]
