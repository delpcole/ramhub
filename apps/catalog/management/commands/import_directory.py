"""
Import real Farmingdale State College faculty from the public campus directory.

Source: apps/catalog/seed_data/farmingdale_directory.ndjson (one JSON object per
line). See the .README.md beside it for the field reference and provenance.

This is the "import tool" the roadmap calls the real plan for getting college
data in. It replaces the fictional professors that seed_demo used to create.

Two rules this command will not bend:

1. **It never writes ratings.** These are real, named people. Every professor it
   creates starts at count=0 with null averages, and on re-import it leaves any
   existing rating_summary completely alone. Ratings come from students on
   RamHub or they do not exist.
2. **It never invents relationships.** The directory says who works here and in
   what department. It does not say who teaches which course, so course_ids is
   left untouched. Guessing that link would put a real person's name on a course
   they may never have taught.

Idempotent on `slug`, the directory's own stable key.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Professor

DATA_FILE = (
    Path(__file__).resolve().parent.parent.parent / "seed_data" / "farmingdale_directory.ndjson"
)

# Fields owned by the college. Overwritten on every import; never edited in-app.
DIRECTORY_FIELDS = (
    "first_name",
    "last_name",
    "department",
    "title",
    "faculty_id",
    "profile_url",
    "department_url",
    "phone",
    "office",
    "directory_retrieved",
)


class Command(BaseCommand):
    help = "Import faculty from the official Farmingdale directory export. Idempotent."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            default=str(DATA_FILE),
            help="Path to the directory .ndjson export.",
        )
        parser.add_argument(
            "--include-staff",
            action="store_true",
            help="Also import non-teaching staff (is_teaching=false). Off by default.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "DESTRUCTIVE: delete professors absent from the file — including any "
                "demo records. Requires --yes."
            ),
        )
        parser.add_argument("--yes", action="store_true", help="Confirm a destructive --prune.")

    def handle(self, *args: Any, **options: Any) -> None:
        rows = self._load(Path(options["file"]), include_staff=options["include_staff"])
        if not rows:
            raise CommandError("No matching rows in the directory file.")

        created, updated = self._upsert(rows)
        pruned = 0
        if options["prune"]:
            pruned = self._prune({row["slug"] for row in rows}, confirmed=options["yes"])

        self._report(created, updated, pruned, len(rows))

    # -- steps -------------------------------------------------------------

    def _load(self, path: Path, *, include_staff: bool) -> list[dict]:
        if not path.exists():
            raise CommandError(f"Directory export not found at {path}")

        rows, seen = [], set()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(f"{path}:{number} is not valid JSON: {exc}") from exc

            if not include_staff and not row.get("is_teaching"):
                continue
            slug = row.get("slug")
            if not slug:
                raise CommandError(f"{path}:{number} has no slug; it cannot be keyed.")
            if slug in seen:
                raise CommandError(f"{path}:{number} repeats slug {slug!r}.")
            seen.add(slug)
            rows.append(row)
        return rows

    def _upsert(self, rows: list[dict]) -> tuple[int, int]:
        created = updated = 0
        for row in rows:
            _, was_created = Professor.objects.update_or_create(
                slug=row["slug"],
                # Only directory-owned fields. rating_summary and course_ids are
                # absent on purpose so an existing record keeps both.
                defaults=self._defaults(row),
            )
            created += was_created
            updated += not was_created
        return created, updated

    def _defaults(self, row: dict) -> dict[str, Any]:
        retrieved = row.get("source_retrieved")
        return {
            "first_name": row.get("first_name") or "",
            "last_name": row.get("last_name") or "",
            "department": row.get("department") or "",
            "title": row.get("title") or "",
            "faculty_id": row.get("faculty_id") or "",
            "profile_url": row.get("profile_url") or "",
            "department_url": row.get("department_url") or "",
            "phone": row.get("phone") or "",
            "office": row.get("location") or "",
            "directory_retrieved": date.fromisoformat(retrieved) if retrieved else None,
        }

    def _prune(self, keep: set[str], *, confirmed: bool) -> int:
        stale = Professor.objects.exclude(slug__in=keep)
        count = stale.count()
        if not count:
            return 0
        if not confirmed:
            raise CommandError(
                f"--prune would delete {count} professor(s) not in the directory file. "
                "Re-run with --yes if that is what you want."
            )
        stale.delete()
        return count

    # -- output ------------------------------------------------------------

    def _report(self, created: int, updated: int, pruned: int, total: int) -> None:
        unrated = Professor.objects.filter(rating_summary__count=0).count()
        self.stdout.write("")
        self.stdout.write(f"  Read        {total:>5} teaching records from the directory")
        self.stdout.write(f"  Professors  {created:>5} created  {updated:>5} updated")
        if pruned:
            self.stdout.write(self.style.WARNING(f"  Pruned      {pruned:>5} not in the file"))
        self.stdout.write("")
        self.stdout.write(
            f"  Totals      {Professor.objects.count()} professors, {unrated} with no ratings yet"
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Directory facts only. No ratings were written — these are real people."
            )
        )
