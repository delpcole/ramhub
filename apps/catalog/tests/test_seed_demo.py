"""
seed_demo has to be safe to run on a database that already has data.

It seeds *courses only*. Professors are real people imported from the college
directory — see test_import_directory.py.
"""

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Course

pytestmark = pytest.mark.django_db


def run_seed(*args) -> str:
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


def counts(output: str, label: str) -> tuple[int, int]:
    """Pull (created, updated) for a line out of the command's summary.

    Parsed rather than substring-matched: "30 created" contains "0 created".
    """
    match = re.search(rf"{label}\s+(\d+) created\s+(\d+) updated", output)
    assert match, f"no {label} line in:\n{output}"
    return int(match.group(1)), int(match.group(2))


def test_seed_creates_the_catalog():
    run_seed()

    assert Course.objects.count() > 50


def test_seed_is_idempotent():
    run_seed()
    courses = Course.objects.count()

    run_seed()

    assert Course.objects.count() == courses


def test_second_run_updates_rather_than_creates():
    first = run_seed()
    second = run_seed()

    first_created, first_updated = counts(first, "Courses")
    second_created, second_updated = counts(second, "Courses")

    assert first_created > 0 and first_updated == 0
    assert second_created == 0 and second_updated == first_created


def test_seed_produces_no_duplicate_course_codes():
    run_seed()
    run_seed()

    codes = list(Course.objects.values_list("code", flat=True))
    assert len(codes) == len(set(codes))


def test_seed_includes_unrated_records_so_that_state_is_reachable():
    run_seed()

    assert Course.objects.filter(rating_summary__count=0).exists()


def test_clear_refuses_without_confirmation():
    run_seed()

    with pytest.raises(CommandError, match="--yes"):
        run_seed("--clear")

    assert Course.objects.count() > 50


def test_clear_with_yes_wipes_then_reseeds():
    run_seed()

    output = run_seed("--clear", "--yes")

    assert "Cleared" in output
    assert Course.objects.count() > 50
