# Generated by Django 3.1.5 on 2021-05-23 00:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0003_fallout_flavor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fallout',
            name='version',
            field=models.CharField(max_length=48),
        ),
    ]