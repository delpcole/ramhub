"""
Add the official-directory fields to Professor, including a unique slug.

`slug` cannot simply be added as unique: any existing rows would all get the
same empty value and collide. So it is added permissively, backfilled from each
professor's name, and only then constrained — the standard three-step pattern
for introducing a unique column to a populated collection.
"""

from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    """Derive a slug for any professor that predates the directory import."""
    Professor = apps.get_model("catalog", "Professor")
    taken: set[str] = set()
    for professor in Professor.objects.all().order_by("pk"):
        base = slugify(f"{professor.first_name} {professor.last_name}") or "professor"
        slug, suffix = base, 2
        while slug in taken:
            slug = f"{base}-{suffix}"
            suffix += 1
        taken.add(slug)
        professor.slug = slug
        professor.save(update_fields=["slug"])


def drop_slugs(apps, schema_editor):
    """Reverse step: nothing to undo, the column goes away with the AddField."""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_professorratingsummary_avg_overall")]

    operations = [
        # 1. permissive
        migrations.AddField(
            model_name="professor",
            name="slug",
            field=models.SlugField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        # the rest of the directory facts
        migrations.AddField(
            model_name="professor",
            name="faculty_id",
            field=models.CharField(blank=True, default="", max_length=16),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="professor",
            name="profile_url",
            field=models.URLField(blank=True, default="", help_text="Official faculty page."),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="professor",
            name="department_url",
            field=models.URLField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="professor",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=32),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="professor",
            name="office",
            field=models.CharField(blank=True, default="", max_length=160),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="professor",
            name="directory_retrieved",
            field=models.DateField(
                blank=True, null=True, help_text="When the directory row was last pulled."
            ),
        ),
        # real directory titles and departments are longer than the demo ones
        migrations.AlterField(
            model_name="professor",
            name="department",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="professor",
            name="title",
            field=models.CharField(
                blank=True, help_text="e.g. Associate Professor.", max_length=160
            ),
        ),
        # 2. backfill
        migrations.RunPython(backfill_slugs, drop_slugs),
        # 3. constrain
        migrations.AlterField(
            model_name="professor",
            name="slug",
            field=models.SlugField(max_length=120, unique=True),
        ),
    ]
