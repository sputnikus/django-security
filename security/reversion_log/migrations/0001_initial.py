# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0001_initial'),
        ('reversion', '0004_auto_20150811_1505'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequestRevision',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('logged_request', models.ForeignKey(verbose_name='logged request', to='security.LoggedRequest')),
                ('revision', models.OneToOneField(verbose_name='revision', to='reversion.Revision')),
            ],
            options={
                'verbose_name': 'Logged request revision',
                'verbose_name_plural': 'Logged requests revisions',
            },
        ),
    ]
