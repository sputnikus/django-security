# Generated by Django 3.1 on 2021-03-26 17:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0002_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='celerytasklog',
            name='triggred_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='trigger time'),
        ),
    ]
