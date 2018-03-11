from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0004_auto_20160530_1608'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='host',
            field=models.CharField(db_index=True, max_length=255, verbose_name='host'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='method',
            field=models.SlugField(max_length=7, verbose_name='method'),
        ),
        migrations.AlterField(
            model_name='inputloggedrequest',
            name='path',
            field=models.CharField(db_index=True, max_length=255, verbose_name='URL path'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='host',
            field=models.CharField(db_index=True, max_length=255, verbose_name='host'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='method',
            field=models.SlugField(max_length=7, verbose_name='method'),
        ),
        migrations.AlterField(
            model_name='outputloggedrequest',
            name='path',
            field=models.CharField(db_index=True, max_length=255, verbose_name='URL path'),
        ),
    ]
