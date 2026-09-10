"""
Import the real Farmingdale course catalog.

Source: apps/catalog/seed_data/farmingdale_courses.ndjson, parsed from the
college's published 2025-2026 course descriptions. See the .README.md beside it
for provenance and caveats, and scrape_catalog.py to regenerate it.

Same two rules as import_directory, for the same reason:

1. **It never writes ratings.** Courses start unrated and a re-import leaves any
   ratings students have left completely alone.
2. **It never invents relationships.** A published catalog says a course exists.
   It does not say who teaches it — that needs section/schedule data — so
   professor_ids is left untouched.

Idempotent on `code`, the catalog's own natural key.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Course

DATA_FILE = (
    Path(__file__).resolve().parent.parent.parent / "seed_data" / "farmingdale_courses.ndjson"
)


class Command(BaseCommand):
    help = "Import courses from the official Farmingdale catalog export. Idempotent."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--file", default=str(DATA_FILE), help="Path to the .ndjson export.")
        parser.add_argument(
            "--prune",
            action="store_true",
            help="DESTRUCTIVE: delete courses absent from the file. Requires --yes.",
        )
        parser.add_argument("--yes", action="store_true", help="Confirm a destructive --prune.")

    def handle(self, *args: Any, **options: Any) -> None:
        rows = self._load(Path(options["file"]))
        created, updated = self._upsert(rows)
        pruned = 0
        if options["prune"]:
            pruned = self._prune({row["code"] for row in rows}, confirmed=options["yes"])
        self._report(created, updated, pruned, len(rows))

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            raise CommandError(f"Catalog export not found at {path}")

        rows, seen = [], set()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(f"{path}:{number} is not valid JSON: {exc}") from exc
            code = (row.get("code") or "").strip()
            if not code:
                raise CommandError(f"{path}:{number} has no course code.")
            if code in seen:
                raise CommandError(f"{path}:{number} repeats code {code!r}.")
            seen.add(code)
            rows.append(row)
        if not rows:
            raise CommandError(f"{path} contained no courses.")
        return rows

    def _upsert(self, rows: list[dict]) -> tuple[int, int]:
        created = updated = 0
        for row in rows:
            _, was_created = Course.objects.update_or_create(
                code=row["code"],
                # rating_summary and professor_ids are absent on purpose, so an
                # existing course keeps both across a re-import.
                defaults={
                    "title": row.get("title") or "",
                    "description": row.get("description") or "",
                    "credits": row.get("credits"),
                    "department": row.get("department") or "",
                    "subject": row.get("subject") or "",
                    "prereq_text": row.get("prerequisites") or "",
                    "coreq_text": row.get("corequisites") or "",
                    "catalog_year": row.get("catalog_year") or "",
                },
            )
            created += was_created
            updated += not was_created
        return created, updated

    def _prune(self, keep: set[str], *, confirmed: bool) -> int:
        stale = Course.objects.exclude(code__in=keep)
        count = stale.count()
        if not count:
            return 0
        if not confirmed:
            raise CommandError(
                f"--prune would delete {count} course(s) not in the catalog file. "
                "Re-run with --yes if that is what you want."
            )
        stale.delete()
        return count

    def _report(self, created: int, updated: int, pruned: int, total: int) -> None:
        no_credits = Course.objects.filter(credits__isnull=True).count()
        self.stdout.write("")
        self.stdout.write(f"  Read        {total:>5} courses from the catalog export")
        self.stdout.write(f"  Courses     {created:>5} created  {updated:>5} updated")
        if pruned:
            self.stdout.write(self.style.WARNING(f"  Pruned      {pruned:>5} not in the file"))
        self.stdout.write("")
        self.stdout.write(
            f"  Totals      {Course.objects.count()} courses, "
            f"{no_credits} with no published credit value"
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Catalog facts only. No ratings were written, and no professors were linked "
                "— a catalog says a course exists, not who teaches it."
            )
        )
