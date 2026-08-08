# Some port names are longer than 64 chars, which broke the index import.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0006_add_filter_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='port',
            name='name',
            field=models.CharField(max_length=128),
        ),
    ]
