# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.db.models.deletion
import json_field.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoggedRequest',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('request_timestamp', models.DateTimeField(verbose_name='Request timestamp')),
                ('method', models.CharField(verbose_name='Method', max_length=7)),
                ('path', models.CharField(verbose_name='URL path', max_length=255)),
                ('queries', json_field.fields.JSONField(help_text='Enter a valid JSON object', verbose_name='Queries', null=True, default='null', blank=True)),
                ('headers', json_field.fields.JSONField(help_text='Enter a valid JSON object', verbose_name='Headers', null=True, default='null', blank=True)),
                ('request_body', models.TextField(verbose_name='Request body', blank=True)),
                ('is_secure', models.BooleanField(verbose_name='HTTPS connection', default=False)),
                ('response_timestamp', models.DateTimeField(verbose_name='Response timestamp')),
                ('response_code', models.PositiveSmallIntegerField(verbose_name='Response code')),
                ('status', models.PositiveSmallIntegerField(verbose_name='Status', choices=[(1, 'Fine'), (2, 'Warning'), (3, 'Error')])),
                ('type', models.PositiveSmallIntegerField(verbose_name='Request type', default=1, choices=[(1, 'Common request'), (2, 'Throttled request'), (3, 'Successful login request'), (4, 'Unsuccessful login request')])),
                ('response_body', models.TextField(verbose_name='Response body', blank=True)),
                ('error_description', models.TextField(verbose_name='Error description', null=True, blank=True)),
                ('ip', models.GenericIPAddressField(verbose_name='IP address')),
                ('user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, blank=True)),
            ],
            options={
                'verbose_name': 'Logged request',
                'ordering': ('-request_timestamp',),
                'verbose_name_plural': 'Logged requests',
            },
        ),
    ]
