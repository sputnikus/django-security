# Generated by Django 3.1.13 on 2021-11-19 18:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security_backends_sql', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='celerytaskinvocationlog',
            options={'ordering': ('-start',)},
        ),
        migrations.AlterModelOptions(
            name='celerytaskrunlog',
            options={'ordering': ('-start',)},
        ),
        migrations.AlterModelOptions(
            name='commandlog',
            options={'ordering': ('-start',)},
        ),
        migrations.AlterModelOptions(
            name='inputrequestlog',
            options={'ordering': ('-start',)},
        ),
        migrations.AlterModelOptions(
            name='outputrequestlog',
            options={'ordering': ('-start',)},
        ),
        migrations.AddField(
            model_name='celerytaskinvocationlog',
            name='release',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='celerytaskrunlog',
            name='release',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='celerytaskrunlog',
            name='waiting_time',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='commandlog',
            name='release',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='inputrequestlog',
            name='release',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='outputrequestlog',
            name='release',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
    ]