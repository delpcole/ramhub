"""
Load demo catalog data so a fresh clone shows a populated directory.

The data lives in ``apps/catalog/seed_data/demo_catalog.json``. Read the
``_meta`` block in that file before trusting any of it: the courses are
hand-written to *resemble* the Farmingdale catalog and are not authoritative.

**Courses only.** Professors are real people now, imported from the official
campus directory by ``manage.py import_directory``. This command used to create
fictional professors with invented ratings; that stopped being acceptable the
moment real names were in the database.

Idempotent. Courses are keyed on ``code``, so running this twice leaves the
database in the same state as running it once. It is safe to run against a
database that already has data.

Note that it does overwrite ``rating_summary`` on every run. That is intentional
while ratings are demo-only — revisit it in the phase that adds a real rating
write path, or this command will start destroying real data.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.catalog.models import Course, CourseRatingSummary

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "seed_data" / "demo_catalog.json"


class Command(BaseCommand):
    help = "Load demo courses and professors into the catalog. Idempotent."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--clear",
            action="store_true",
            help="DESTRUCTIVE: delete every Course and Professor first. Requires --yes.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm a destructive --clear without being prompted.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        data = self._load()

        if options["clear"]:
            self._clear(confirmed=options["yes"])

        _, course_stats = self._seed_courses(data["courses"])

        self._report(course_stats)

    # -- steps -------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not DATA_FILE.exists():
            raise CommandError(f"Seed data not found at {DATA_FILE}")
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"{DATA_FILE} is not valid JSON: {exc}") from exc

    def _clear(self, *, confirmed: bool) -> None:
        """Only ever touches courses. Imported faculty are not this command's data."""
        count = Course.objects.count()
        if not confirmed:
            raise CommandError(
                f"--clear would delete {count} courses. Re-run with --yes if that is what you want."
            )
        Course.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"Cleared {count} courses."))

    def _seed_courses(self, rows: list[dict]) -> tuple[dict[str, Course], tuple[int, int]]:
        created = updated = 0
        by_code: dict[str, Course] = {}
        for row in rows:
            summary = CourseRatingSummary(**row["rating_summary"])
            defaults = {
                "title": row["title"],
                "description": row["description"],
                "credits": row["credits"],
                "department": row["department"],
                "prereq_text": row["prereq_text"],
                "rating_summary": summary,
            }
            try:
                course, was_created = Course.objects.update_or_create(
                    code=row["code"], defaults=defaults
                )
            except IntegrityError as exc:  # pragma: no cover - duplicate code in the fixture
                raise CommandError(f"Duplicate course code {row['code']} in seed data.") from exc
            created += was_created
            updated += not was_created
            by_code[course.code] = course
        return by_code, (created, updated)

    # -- output ------------------------------------------------------------

    def _report(self, course_stats: tuple[int, int]) -> None:
        created, updated = course_stats
        unrated = Course.objects.filter(rating_summary__count=0).count()

        self.stdout.write("")
        self.stdout.write(f"  Courses     {created:>4} created  {updated:>4} updated")
        self.stdout.write("")
        self.stdout.write(
            f"  Totals      {Course.objects.count()} courses ({unrated} with no ratings yet)"
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo courses loaded. They are representative, not authoritative. "
                "Run `manage.py import_directory` for real faculty."
            )
        )
