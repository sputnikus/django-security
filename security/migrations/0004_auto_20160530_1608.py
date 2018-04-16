import jsonfield.fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0003_auto_20160509_1622'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='queries',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='queries'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='request_headers',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='request headers'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='response_headers',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='response headers'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='queries',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='queries'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='request_headers',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='request headers'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='response_headers',
            field=jsonfield.fields.JSONField(blank=True, null=True, verbose_name='response headers'),
        ),
    ]
