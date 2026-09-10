"""
The directory import brings in real, named people. The rules it must not break:
never write ratings, never invent course assignments, never duplicate.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Professor, ProfessorRatingSummary

pytestmark = pytest.mark.django_db


def row(slug, first, last, *, teaching=True, **extra):
    base = {
        "slug": slug,
        "first_name": first,
        "last_name": last,
        "display_name": f"{first} {last}",
        "group": "faculty" if teaching else "staff",
        "is_teaching": teaching,
        "title": "Associate Professor",
        "department": "Computer Science",
        "department_url": "https://www.farmingdale.edu/cs/",
        "faculty_id": "303",
        "profile_url": "https://www.farmingdale.edu/faculty/?fid=303",
        "phone": "934-420-2739",
        "location": "Whitman Hall, Room 100",
        "source_retrieved": "2026-09-10",
    }
    base.update(extra)
    return base


@pytest.fixture
def directory_file(tmp_path):
    def _write(rows):
        path = tmp_path / "directory.ndjson"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return str(path)

    return _write


def run_import(path, *args) -> str:
    out = StringIO()
    call_command("import_directory", "--file", path, *args, stdout=out)
    return out.getvalue()


# -- the basics ------------------------------------------------------------
def test_import_creates_professors(directory_file):
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])

    run_import(path)

    professor = Professor.objects.get(slug="ada-lovelace")
    assert professor.full_name == "Ada Lovelace"
    assert professor.title == "Associate Professor"
    assert professor.office == "Whitman Hall, Room 100"
    assert professor.phone == "934-420-2739"
    assert professor.profile_url.endswith("fid=303")
    assert str(professor.directory_retrieved) == "2026-09-10"


def test_import_is_idempotent(directory_file):
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])

    run_import(path)
    run_import(path)

    assert Professor.objects.filter(slug="ada-lovelace").count() == 1


def test_import_updates_changed_directory_facts(directory_file):
    run_import(directory_file([row("ada-lovelace", "Ada", "Lovelace")]))

    run_import(directory_file([row("ada-lovelace", "Ada", "Lovelace", title="Professor")]))

    assert Professor.objects.get(slug="ada-lovelace").title == "Professor"


def test_staff_are_skipped_unless_asked_for(directory_file):
    path = directory_file(
        [
            row("ada-lovelace", "Ada", "Lovelace"),
            row("sam-clerk", "Sam", "Clerk", teaching=False),
        ]
    )

    run_import(path)
    assert {p.slug for p in Professor.objects.all()} == {"ada-lovelace"}

    run_import(path, "--include-staff")
    assert Professor.objects.count() == 2


# -- the rules that matter most -------------------------------------------
def test_import_never_writes_ratings(directory_file):
    """Real people start unrated. Ratings come from students or not at all."""
    run_import(directory_file([row("ada-lovelace", "Ada", "Lovelace")]))

    summary = Professor.objects.get(slug="ada-lovelace").rating_summary
    assert summary.count == 0
    assert summary.avg_clarity is None
    assert summary.avg_overall is None


def test_reimport_preserves_ratings_earned_on_ramhub(directory_file):
    """A directory refresh must not wipe student reviews."""
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])
    run_import(path)

    professor = Professor.objects.get(slug="ada-lovelace")
    professor.rating_summary = ProfessorRatingSummary(
        avg_clarity=4.5, avg_helpfulness=4.2, avg_fairness=4.0, avg_overall=4.23, count=12
    )
    professor.save()

    run_import(path)

    summary = Professor.objects.get(slug="ada-lovelace").rating_summary
    assert summary.count == 12
    assert summary.avg_overall == 4.23


def test_reimport_preserves_course_links(directory_file, make_course):
    """The directory says who works here, not who teaches what."""
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])
    run_import(path)

    course = make_course(code="CSC 240")
    professor = Professor.objects.get(slug="ada-lovelace")
    professor.course_ids = [course.pk]
    professor.save()

    run_import(path)

    assert Professor.objects.get(slug="ada-lovelace").course_ids == [course.pk]


# -- failure modes ---------------------------------------------------------
def test_missing_file_is_a_clean_error():
    with pytest.raises(CommandError, match="not found"):
        run_import("/tmp/does-not-exist.ndjson")


def test_malformed_json_names_the_line(directory_file, tmp_path):
    path = tmp_path / "bad.ndjson"
    path.write_text('{"slug": "ok", "is_teaching": true}\nnot json\n', encoding="utf-8")

    with pytest.raises(CommandError, match=":2"):
        run_import(str(path))


def test_duplicate_slugs_are_rejected(directory_file):
    path = directory_file(
        [
            row("ada-lovelace", "Ada", "Lovelace"),
            row("ada-lovelace", "Ada", "Lovelace"),
        ]
    )

    with pytest.raises(CommandError, match="repeats slug"):
        run_import(path)


def test_prune_refuses_without_confirmation(directory_file, make_professor):
    make_professor(first_name="Old", last_name="Demo")
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])

    with pytest.raises(CommandError, match="--yes"):
        run_import(path, "--prune")

    assert Professor.objects.filter(slug="old-demo").exists()


def test_prune_with_yes_removes_records_not_in_the_directory(directory_file, make_professor):
    make_professor(first_name="Old", last_name="Demo")
    path = directory_file([row("ada-lovelace", "Ada", "Lovelace")])

    run_import(path, "--prune", "--yes")

    assert {p.slug for p in Professor.objects.all()} == {"ada-lovelace"}


# -- the shipped export ----------------------------------------------------
def test_the_bundled_directory_export_is_usable():
    """Guards the real file: valid NDJSON, unique slugs, and teaching rows present."""
    from apps.catalog.management.commands.import_directory import DATA_FILE

    assert DATA_FILE.exists(), "the directory export should be committed"

    slugs, teaching = set(), 0
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        assert record["slug"] not in slugs, f"duplicate slug {record['slug']}"
        slugs.add(record["slug"])
        if record.get("is_teaching"):
            teaching += 1
            assert record.get("department"), f"{record['slug']} has no department"

    assert teaching > 800
