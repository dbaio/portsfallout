# One row per build log: merge the pairs the crawler and `find_orphan_fallouts`
# stored for the same log, keeping the row with the report, and have the
# database refuse another.

from django.db import migrations, models
from django.db.models import Count

# What the kept row may be missing that its double can supply.
FILLABLE = ['report_url', 'flavor', 'server', 'package_name',
            'ports_top_commit', 'port_dir_commit', 'poudriere_version',
            'host_osversion', 'jail_osversion']


def merge_duplicates(apps, schema_editor):
    Fallout = apps.get_model('ports', 'Fallout')

    repeated = (Fallout.objects.values('log_url')
                .annotate(rows=Count('id')).filter(rows__gt=1)
                .values_list('log_url', flat=True))

    for log_url in list(repeated):
        rows = list(Fallout.objects.filter(log_url=log_url).order_by('id'))
        # The row with the report is the crawler's, whose phase came from the
        # mail rather than from the head of the log.
        kept = next((row for row in rows if row.report_url), rows[0])

        for row in rows:
            if row is kept:
                continue
            for field in FILLABLE:
                if not getattr(kept, field) and getattr(row, field):
                    setattr(kept, field, getattr(row, field))
            row.delete()

        kept.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ports', '0008_fallout_log_details'),
    ]

    operations = [
        migrations.RunPython(merge_duplicates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='fallout',
            name='log_url',
            field=models.URLField(unique=True),
        ),
    ]
