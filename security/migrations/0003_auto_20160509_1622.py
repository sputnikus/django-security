import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import jsonfield.fields


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ContentType.objects.filter(app_label='security', model='loggedrequest').update(model='inputloggedrequest')


def migrate_request_status(apps, schema_editor):
    InputLoggedRequest = apps.get_model('security', 'InputLoggedRequest')
    for old_status, new_status in ((1, 20), (2, 30), (3, 50)):
        InputLoggedRequest.objects.filter(status=old_status).update(status=new_status)


class Migration(migrations.Migration):
    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('security', '0002_auto_20151014_2159'),
    ]

    operations = [
        # Migrate LoggedRequest to InputLoggedRequest
        migrations.RenameModel('LoggedRequest', 'InputLoggedRequest'),
        migrations.RunPython(update_content_types),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='request_body',
            field=models.TextField(blank=True, verbose_name='request body'),
        ),
        migrations.RunPython(migrate_request_status),
        # Rename and alter InputLoggedRequest.headers field
        migrations.RenameField(
            model_name='inputloggedrequest',
            old_name='headers',
            new_name='request_headers',
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='request_headers',
            field=jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                             null=True, verbose_name='request headers'),
        ),
        # Alter other InputLoggedRequest fields
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterModelOptions(
            name='inputloggedrequest',
            options={'ordering': ('-request_timestamp',), 'verbose_name': 'input logged request',
                     'verbose_name_plural': 'input logged requests'},
        ),
        migrations.AddField(
            model_name='inputloggedrequest',
            name='exception_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='exception name'),
        ),
        migrations.AddField(
            model_name='inputloggedrequest',
            name='host',
            field=models.CharField(default='empty', max_length=255, verbose_name='host'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='inputloggedrequest',
            name='response_headers',
            field=jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                             null=True, verbose_name='response headers'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='error_description',
            field=models.TextField(blank=True, null=True, verbose_name='error description'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='method',
            field=models.CharField(max_length=7, verbose_name='method'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='queries',
            field=jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                             null=True, verbose_name='queries'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='request_body',
            field=models.TextField(blank=True, verbose_name='request body'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='request_timestamp',
            field=models.DateTimeField(db_index=True, verbose_name='request timestamp'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='response_body',
            field=models.TextField(blank=True, null=True, verbose_name='response body'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='response_code',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='response code'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='response_timestamp',
            field=models.DateTimeField(blank=True, null=True, verbose_name='response timestamp'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='status',
            field=models.PositiveSmallIntegerField(
                choices=[(20, 'Info'), (30, 'Warning'), (40, 'Error'), (10, 'Debug'), (50, 'Critical')],
                verbose_name='status'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='type',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'Common request'), (2, 'Throttled request'), (3, 'Successful login request'),
                         (4, 'Unsuccessful login request')], default=1, verbose_name='type'),
        ),

        migrations.CreateModel(
            name='OutputLoggedRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.CharField(max_length=255, verbose_name='host')),
                ('method', models.CharField(max_length=7, verbose_name='method')),
                ('path', models.CharField(max_length=255, verbose_name='URL path')),
                ('queries',
                 jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                            null=True, verbose_name='queries')),
                ('is_secure', models.BooleanField(default=False, verbose_name='HTTPS connection')),
                ('request_timestamp', models.DateTimeField(db_index=True, verbose_name='request timestamp')),
                ('request_headers',
                 jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                            null=True, verbose_name='request headers')),
                ('request_body', models.TextField(blank=True, verbose_name='request body')),
                ('response_timestamp', models.DateTimeField(blank=True, null=True, verbose_name='response timestamp')),
                (
                'response_code', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='response code')),
                ('response_headers',
                 jsonfield.fields.JSONField(blank=True, default='null', help_text='Enter a valid JSON object',
                                            null=True, verbose_name='response headers')),
                ('response_body', models.TextField(blank=True, null=True, verbose_name='response body')),
                ('status', models.PositiveSmallIntegerField(
                    choices=[(20, 'Info'), (30, 'Warning'), (40, 'Error'), (10, 'Debug'), (50, 'Critical')],
                    verbose_name='status')),
                ('error_description', models.TextField(blank=True, null=True, verbose_name='error description')),
                ('exception_name',
                 models.CharField(blank=True, max_length=255, null=True, verbose_name='exception name')),
                ('slug', models.SlugField(blank=True, null=True, verbose_name='slug')),
            ],
            options={
                'verbose_name': 'output logged request',
                'verbose_name_plural': 'output logged requests',
                'ordering': ('-request_timestamp',),
            },
        ),
        migrations.CreateModel(
            name='OutputLoggedRequestRelatedObjects',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('content_type',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('output_logged_request',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_objects',
                                   to='security.OutputLoggedRequest', verbose_name='output logged requests')),
            ],
        )
    ]
