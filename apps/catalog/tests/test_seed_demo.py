"""seed_demo has to be safe to run on a database that already has data."""

import re
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Course, Professor

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
    assert Professor.objects.count() > 20


def test_seed_is_idempotent():
    run_seed()
    courses, professors = Course.objects.count(), Professor.objects.count()

    run_seed()

    assert Course.objects.count() == courses
    assert Professor.objects.count() == professors


def test_second_run_updates_rather_than_creates():
    first = run_seed()
    second = run_seed()

    first_created, first_updated = counts(first, "Courses")
    second_created, second_updated = counts(second, "Courses")

    assert first_created > 0 and first_updated == 0
    assert second_created == 0 and second_updated == first_created

    assert counts(second, "Professors")[0] == 0


def test_seed_produces_no_duplicate_course_codes():
    run_seed()
    run_seed()

    codes = list(Course.objects.values_list("code", flat=True))
    assert len(codes) == len(set(codes))


def test_seed_links_every_course_and_professor_in_both_directions():
    run_seed()

    courses = {c.pk: c for c in Course.objects.all()}
    professors = {p.pk: p for p in Professor.objects.all()}

    for course in courses.values():
        for professor_id in course.professor_ids:
            assert professor_id in professors
            assert course.pk in professors[professor_id].course_ids

    for professor in professors.values():
        for course_id in professor.course_ids:
            assert course_id in courses
            assert professor.pk in courses[course_id].professor_ids


def test_reseeding_does_not_duplicate_entries_in_the_id_arrays():
    """The arrays are rebuilt each run, not appended to."""
    run_seed()
    run_seed()

    for course in Course.objects.all():
        assert len(course.professor_ids) == len(set(course.professor_ids))
    for professor in Professor.objects.all():
        assert len(professor.course_ids) == len(set(professor.course_ids))


def test_seed_includes_unrated_records_so_that_state_is_reachable():
    run_seed()

    assert Course.objects.filter(rating_summary__count=0).exists()
    assert Professor.objects.filter(rating_summary__count=0).exists()


def test_seeded_professors_have_a_stored_overall():
    """The professors directory sorts on it, so it cannot be left null."""
    run_seed()

    rated = Professor.objects.exclude(rating_summary__count=0)
    assert rated.exists()
    for professor in rated:
        assert professor.rating_summary.avg_overall is not None


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
