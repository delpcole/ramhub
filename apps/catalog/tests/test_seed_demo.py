"""seed_demo is a wrapper: it runs both real imports, in order."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.catalog.models import Course, Professor, ProfessorRatingSummary

pytestmark = pytest.mark.django_db


def test_seed_demo_loads_both_directories():
    out = StringIO()
    call_command("seed_demo", stdout=out)

    assert Course.objects.count() > 1500
    assert Professor.objects.count() > 800
    assert "import_catalog" in out.getvalue()
    assert "import_directory" in out.getvalue()


def test_seed_demo_leaves_courses_unrated():
    """No course has a rating until a student leaves one."""
    call_command("seed_demo", stdout=StringIO())

    assert not Course.objects.exclude(rating_summary__count=0).exists()


def test_every_professor_rating_is_tagged_as_imported():
    """
    seed_demo does write professor ratings, from RateMyProfessors. Every one of
    them must carry source="rmp" — an untagged rating would be displayed as a
    RamHub student review, which it is not.
    """
    call_command("seed_demo", stdout=StringIO())

    rated = Professor.objects.exclude(rating_summary__count=0)
    assert rated.exists(), "the RMP import should have rated some professors"
    for professor in rated:
        assert professor.rating_summary.source == ProfessorRatingSummary.SOURCE_RMP


def test_professors_with_ratings_have_a_rank_score():
    """Otherwise they sort as null and the "Highest rated" order is meaningless."""
    call_command("seed_demo", stdout=StringIO())

    for professor in Professor.objects.exclude(rating_summary__count=0)[:50]:
        assert professor.rating_summary.rank_score is not None


def test_seed_demo_is_idempotent():
    call_command("seed_demo", stdout=StringIO())
    courses, professors = Course.objects.count(), Professor.objects.count()

    call_command("seed_demo", stdout=StringIO())

    assert Course.objects.count() == courses
    assert Professor.objects.count() == professors
