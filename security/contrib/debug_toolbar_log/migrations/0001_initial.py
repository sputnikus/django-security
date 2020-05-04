from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0001_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='DebugToolbarData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('logged_request',models.OneToOneField(
                    on_delete=models.deletion.CASCADE, related_name='input_logged_request_toolbar',
                    to='security.InputLoggedRequest', verbose_name='logged request'
                )),
                ('toolbar',  models.TextField(verbose_name='toolbar', null=False, blank=False,)),
            ],
            options={
                'verbose_name': 'Logged request toolbar',
                'verbose_name_plural': 'Logged requests toolbars',
            },
        ),
    ]
