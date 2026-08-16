# The fields read from the poudriere header of the build log.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0007_widen_port_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='fallout',
            name='host_osversion',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='fallout',
            name='jail_osversion',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name='fallout',
            name='package_name',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='fallout',
            name='port_dir_commit',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='fallout',
            name='ports_top_commit',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='fallout',
            name='poudriere_version',
            field=models.CharField(blank=True, max_length=48),
        ),
    ]
