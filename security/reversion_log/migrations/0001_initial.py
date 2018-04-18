from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reversion', '__first__'),
        ('security', '0003_auto_20160509_1622'),
    ]

    operations = [
        migrations.CreateModel(
            name='InputRequestRevision',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('logged_request', models.ForeignKey(verbose_name='logged request', to='security.InputLoggedRequest',
                                                     on_delete=models.CASCADE)),
                ('revision', models.OneToOneField(verbose_name='revision', to='reversion.Revision',
                                                  on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name': 'Logged request revision',
                'verbose_name_plural': 'Logged requests revisions',
            },
        ),
    ]
