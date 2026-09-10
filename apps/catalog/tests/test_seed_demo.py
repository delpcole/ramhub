"""seed_demo is a wrapper: it runs both real imports, in order."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.catalog.models import Course, Professor

pytestmark = pytest.mark.django_db


def test_seed_demo_loads_both_directories():
    out = StringIO()
    call_command("seed_demo", stdout=out)

    assert Course.objects.count() > 1500
    assert Professor.objects.count() > 800
    assert "import_catalog" in out.getvalue()
    assert "import_directory" in out.getvalue()


def test_seed_demo_writes_no_ratings():
    """Nothing on RamHub has a rating until a student leaves one."""
    call_command("seed_demo", stdout=StringIO())

    assert not Course.objects.exclude(rating_summary__count=0).exists()
    assert not Professor.objects.exclude(rating_summary__count=0).exists()


def test_seed_demo_is_idempotent():
    call_command("seed_demo", stdout=StringIO())
    courses, professors = Course.objects.count(), Professor.objects.count()

    call_command("seed_demo", stdout=StringIO())

    assert Course.objects.count() == courses
    assert Professor.objects.count() == professors
