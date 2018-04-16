import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('security', '0006_auto_20171002_1415'),
    ]

    operations = [
        migrations.AddField(
            model_name='outputloggedrequest',
            name='input_logged_request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='security.InputLoggedRequest', verbose_name='input logged request'),
        ),
    ]
