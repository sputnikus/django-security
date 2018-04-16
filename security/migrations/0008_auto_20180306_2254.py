from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('security', '0007_outputloggedrequest_input_logged_request'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommandLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.DateTimeField(editable=False, verbose_name='start')),
                ('stop', models.DateTimeField(blank=True, editable=False, null=True, verbose_name='stop')),
                ('command_name',
                 models.CharField(db_index=True, editable=False, max_length=250, verbose_name='command name')),
                ('command_options', models.TextField(editable=False, verbose_name='command options')),
                ('executed_from_command_line',
                 models.BooleanField(default=False, editable=False, verbose_name='executed from command line')),
                ('output', models.TextField(blank=True, editable=False, null=True, verbose_name='command output')),
                ('is_successful',
                 models.BooleanField(default=False, editable=False, verbose_name='finished successfully')),
            ],
            options={
                'verbose_name': 'command log',
                'ordering': ('-start',),
                'verbose_name_plural': 'command logs',
            },
        ),
    ]
