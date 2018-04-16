from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0005_auto_20161218_2224'),
    ]

    operations = [
        migrations.AddField(
            model_name='inputloggedrequest',
            name='slug',
            field=models.SlugField(blank=True, max_length=255, null=True, verbose_name='slug'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='slug',
            field=models.SlugField(blank=True, max_length=255, null=True, verbose_name='slug'),
        ),
    ]
