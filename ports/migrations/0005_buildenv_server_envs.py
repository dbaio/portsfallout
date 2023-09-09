# Generated by Django 4.1.3 on 2023-09-07 21:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0004_auto_20210523_0034'),
    ]

    operations = [
        migrations.CreateModel(
            name='BuildEnv',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=48, unique=True)),
            ],
            options={
                'verbose_name_plural': 'Envs',
            },
        ),
        migrations.AddField(
            model_name='server',
            name='envs',
            field=models.ManyToManyField(to='ports.buildenv'),
        ),
    ]
