# The version the port has in the ports tree, filled by the INDEX import.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0009_fallout_log_url_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='port',
            name='version',
            field=models.CharField(blank=True, max_length=48),
        ),
    ]
