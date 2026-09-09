"""
Load demo catalog data so a fresh clone shows a populated directory.

The data lives in ``apps/catalog/seed_data/demo_catalog.json``. Read the
``_meta`` block in that file before trusting any of it: the courses are
hand-written to *resemble* the Farmingdale catalog and the professors are
entirely fictional. Neither is authoritative.

Idempotent. Courses are keyed on ``code`` and professors on
(first name, last name, department), so running this twice leaves the database
in the same state as running it once. It is safe to run against a database that
already has data.

Note that it does overwrite ``rating_summary`` on every run. That is intentional
while ratings are demo-only — revisit it in the phase that adds a real rating
write path, or this command will start destroying real data.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.catalog.models import (
    Course,
    CourseRatingSummary,
    Professor,
    ProfessorRatingSummary,
)

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

        courses, course_stats = self._seed_courses(data["courses"])
        professors, prof_stats = self._seed_professors(data["professors"])
        links = self._link(data["professors"], courses, professors)

        self._report(course_stats, prof_stats, links)

    # -- steps -------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not DATA_FILE.exists():
            raise CommandError(f"Seed data not found at {DATA_FILE}")
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"{DATA_FILE} is not valid JSON: {exc}") from exc

    def _clear(self, *, confirmed: bool) -> None:
        n_c, n_p = Course.objects.count(), Professor.objects.count()
        if not confirmed:
            raise CommandError(
                f"--clear would delete {n_c} courses and {n_p} professors. "
                "Re-run with --yes if that is what you want."
            )
        Course.objects.all().delete()
        Professor.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"Cleared {n_c} courses and {n_p} professors."))

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

    def _seed_professors(self, rows: list[dict]) -> tuple[dict[str, Professor], tuple[int, int]]:
        created = updated = 0
        by_name: dict[str, Professor] = {}
        for row in rows:
            summary = ProfessorRatingSummary(**row["rating_summary"])
            professor, was_created = Professor.objects.update_or_create(
                first_name=row["first_name"],
                last_name=row["last_name"],
                department=row["department"],
                defaults={
                    "title": row["title"],
                    "photo": row["photo"],
                    "bio": row["bio"],
                    "rating_summary": summary,
                },
            )
            created += was_created
            updated += not was_created
            by_name[f"{professor.first_name} {professor.last_name}"] = professor
        return by_name, (created, updated)

    def _link(
        self,
        rows: list[dict],
        courses: dict[str, Course],
        professors: dict[str, Professor],
    ) -> int:
        """
        Write both sides of the Course <-> Professor relationship.

        There is no ManyToManyField here, so nothing keeps the two arrays in
        sync for us — both are rebuilt from scratch on every run, which is what
        makes re-running idempotent instead of appending duplicates.
        """
        course_to_profs: dict[str, list] = {code: [] for code in courses}
        for row in rows:
            name = f"{row['first_name']} {row['last_name']}"
            professor = professors[name]
            taught = [courses[code] for code in row["teaches"] if code in courses]
            professor.course_ids = [c.pk for c in taught]
            professor.save(update_fields=["course_ids"])
            for course in taught:
                course_to_profs[course.code].append(professor.pk)

        for code, professor_ids in course_to_profs.items():
            course = courses[code]
            course.professor_ids = professor_ids
            course.save(update_fields=["professor_ids"])

        return sum(len(v) for v in course_to_profs.values())

    # -- output ------------------------------------------------------------

    def _report(
        self, course_stats: tuple[int, int], prof_stats: tuple[int, int], links: int
    ) -> None:
        c_created, c_updated = course_stats
        p_created, p_updated = prof_stats
        unrated_c = Course.objects.filter(rating_summary__count=0).count()
        unrated_p = Professor.objects.filter(rating_summary__count=0).count()

        self.stdout.write("")
        self.stdout.write(f"  Courses     {c_created:>4} created  {c_updated:>4} updated")
        self.stdout.write(f"  Professors  {p_created:>4} created  {p_updated:>4} updated")
        self.stdout.write(f"  Links       {links:>4} course-professor pairs (both directions)")
        self.stdout.write("")
        self.stdout.write(
            f"  Totals      {Course.objects.count()} courses "
            f"({unrated_c} with no ratings yet), "
            f"{Professor.objects.count()} professors ({unrated_p} with no ratings yet)"
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo data loaded. Courses are representative; professors are fictional."
            )
        )
