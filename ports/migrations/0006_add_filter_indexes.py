# Index the columns the fallout/port filters and the date ordering run against.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0005_buildenv_server_envs'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fallout',
            name='category',
            field=models.CharField(db_index=True, max_length=48),
        ),
        migrations.AlterField(
            model_name='fallout',
            name='date',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='fallout',
            name='env',
            field=models.CharField(db_index=True, max_length=48),
        ),
        migrations.AlterField(
            model_name='fallout',
            name='maintainer',
            field=models.EmailField(db_index=True, max_length=254),
        ),
        migrations.AlterField(
            model_name='port',
            name='maintainer',
            field=models.EmailField(db_index=True, max_length=254),
        ),
    ]
