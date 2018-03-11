from django.db import migrations, models


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
