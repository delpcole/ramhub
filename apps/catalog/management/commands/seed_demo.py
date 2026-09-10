"""
Fill a local database with everything the site needs to be usable.

CLAUDE.md documents `seed_demo` as the one command to run after `migrate`, so it
stays — but there is no demo data left behind it. Both directories are populated
from real, official Farmingdale sources now, and this simply runs the two
imports in order:

    manage.py import_catalog     ~1,785 courses from the published catalog
    manage.py import_directory   ~913 teaching staff from the campus directory
    manage.py import_rmp         RateMyProfessors scores onto matching faculty

Run any of them directly. All three are idempotent.

Note what the third one does: it writes professor ratings that RamHub did not
receive from its own students. Those are tagged source="rmp" and labelled as
RateMyProfessors data wherever they appear. Courses are never rated this way —
no course has a rating until a student leaves one.
"""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.catalog.models import Course, Professor


class Command(BaseCommand):
    help = "Load real courses, faculty and RMP ratings. Runs the three imports in order."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Pass --prune to both imports, dropping records no longer in the exports.",
        )
        parser.add_argument("--yes", action="store_true", help="Confirm a destructive --prune.")

    def handle(self, *args: Any, **options: Any) -> None:
        extra = []
        if options["prune"]:
            extra.append("--prune")
        if options["yes"]:
            extra.append("--yes")

        for command in ("import_catalog", "import_directory"):
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{command}"))
            call_command(command, *extra, stdout=self.stdout, stderr=self.stderr)

        # import_rmp has no --prune; it must run last, after the faculty it
        # matches against exist.
        self.stdout.write(self.style.MIGRATE_HEADING("\nimport_rmp"))
        call_command("import_rmp", stdout=self.stdout, stderr=self.stderr)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Ready: {Course.objects.count()} courses and "
                f"{Professor.objects.count()} professors. Courses and faculty come from "
                f"the college; professor ratings come from RateMyProfessors, not RamHub."
            )
        )
