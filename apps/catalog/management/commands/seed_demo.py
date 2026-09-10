"""
Fill a local database with everything the site needs to be usable.

CLAUDE.md documents `seed_demo` as the one command to run after `migrate`, so it
stays — but there is no demo data left behind it. Both directories are populated
from real, official Farmingdale sources now, and this simply runs the two
imports in order:

    manage.py import_catalog     ~1,785 courses from the published catalog
    manage.py import_directory   ~913 teaching staff from the campus directory

Run either directly if you only want one of them. Both are idempotent, and
neither writes ratings — no course or professor on RamHub has a rating until a
student leaves one.
"""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.catalog.models import Course, Professor


class Command(BaseCommand):
    help = "Load real courses and faculty. Runs import_catalog then import_directory."

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

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Ready: {Course.objects.count()} courses and "
                f"{Professor.objects.count()} professors, all from official sources."
            )
        )
