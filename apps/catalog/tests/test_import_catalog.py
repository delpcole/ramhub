"""
The catalog import loads real, published courses. Same rules as the directory
import: never write ratings, never invent relationships.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import Course, CourseRatingSummary

pytestmark = pytest.mark.django_db


def row(code, title="A Course", **extra):
    base = {
        "code": code,
        "subject": code.split(" ")[0],
        "title": title,
        "description": "A description of the course.",
        "credits": 3,
        "credits_text": "3 (3,0)",
        "prerequisites": "",
        "corequisites": "",
        "department": "Computer Science",
        "department_code": code.split(" ")[0],
        "catalog_year": "2025-2026",
    }
    base.update(extra)
    return base


@pytest.fixture
def catalog_file(tmp_path):
    def _write(rows):
        path = tmp_path / "courses.ndjson"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return str(path)

    return _write


def run_import(path, *args) -> str:
    out = StringIO()
    call_command("import_catalog", "--file", path, *args, stdout=out)
    return out.getvalue()


# -- the basics ------------------------------------------------------------
def test_import_creates_courses(catalog_file):
    path = catalog_file(
        [
            row("CSC 229", "Data Structures & Algorithms I", prerequisites="CSC 111"),
        ]
    )

    run_import(path)

    course = Course.objects.get(code="CSC 229")
    assert course.title == "Data Structures & Algorithms I"
    assert course.credits == 3
    assert course.prereq_text == "CSC 111"
    assert course.catalog_year == "2025-2026"
    assert course.subject == "CSC"


def test_import_is_idempotent(catalog_file):
    path = catalog_file([row("CSC 229")])

    run_import(path)
    run_import(path)

    assert Course.objects.filter(code="CSC 229").count() == 1


def test_courses_without_published_credits_stay_null(catalog_file):
    """23 real catalog entries publish no credit value. Guessing one would lie."""
    path = catalog_file([row("AFR 101", credits=None)])

    run_import(path)

    assert Course.objects.get(code="AFR 101").credits is None


# -- the rules that matter most -------------------------------------------
def test_import_never_writes_ratings(catalog_file):
    run_import(catalog_file([row("CSC 229")]))

    summary = Course.objects.get(code="CSC 229").rating_summary
    assert summary.count == 0
    assert summary.avg_difficulty is None


def test_reimport_preserves_ratings_earned_on_ramhub(catalog_file):
    path = catalog_file([row("CSC 229")])
    run_import(path)

    course = Course.objects.get(code="CSC 229")
    course.rating_summary = CourseRatingSummary(
        avg_difficulty=4.1, avg_workload=4.0, avg_usefulness=4.4, count=12
    )
    course.save()

    run_import(path)

    assert Course.objects.get(code="CSC 229").rating_summary.count == 12


def test_reimport_preserves_professor_links(catalog_file, make_professor):
    """A catalog says a course exists, not who teaches it."""
    path = catalog_file([row("CSC 229")])
    run_import(path)

    professor = make_professor()
    course = Course.objects.get(code="CSC 229")
    course.professor_ids = [professor.pk]
    course.save()

    run_import(path)

    assert Course.objects.get(code="CSC 229").professor_ids == [professor.pk]


# -- failure modes ---------------------------------------------------------
def test_missing_file_is_a_clean_error():
    with pytest.raises(CommandError, match="not found"):
        run_import("/tmp/no-such-catalog.ndjson")


def test_duplicate_codes_are_rejected(catalog_file):
    with pytest.raises(CommandError, match="repeats code"):
        run_import(catalog_file([row("CSC 229"), row("CSC 229")]))


def test_prune_refuses_without_confirmation(catalog_file, make_course):
    make_course(code="OLD 100")

    with pytest.raises(CommandError, match="--yes"):
        run_import(catalog_file([row("CSC 229")]), "--prune")

    assert Course.objects.filter(code="OLD 100").exists()


def test_prune_with_yes_removes_courses_not_in_the_catalog(catalog_file, make_course):
    make_course(code="OLD 100")

    run_import(catalog_file([row("CSC 229")]), "--prune", "--yes")

    assert {c.code for c in Course.objects.all()} == {"CSC 229"}


# -- the shipped export ----------------------------------------------------
def test_the_bundled_catalog_export_is_usable():
    from apps.catalog.management.commands.import_catalog import DATA_FILE

    assert DATA_FILE.exists(), "the catalog export should be committed"

    codes = set()
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        assert record["code"] not in codes, f"duplicate code {record['code']}"
        codes.add(record["code"])
        assert record["title"], f"{record['code']} has no title"
        assert record["description"], f"{record['code']} has no description"

    assert len(codes) > 1500
    # the codes RamHub demos with should be real
    assert {"CSC 111", "CSC 229", "MTH 150", "EGL 101"} <= codes


def test_no_catalog_metadata_leaked_into_descriptions():
    """
    The catalog punctuates "Prerequisite(s):" half a dozen ways. If the parser
    misses a variant it lands in the description instead of the prereq field.
    """
    import re

    from apps.catalog.management.commands.import_catalog import DATA_FILE

    label = re.compile(
        r"(?m)^[ \t]*(Prerequisites?\s*\(?s?\)?|Corequisites?\s*\(?s?\)?|Credits)[ \t]*[:;]"
    )
    offenders = []
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if label.search(record["description"]):
            offenders.append(record["code"])

    assert not offenders, f"metadata leaked into descriptions: {offenders[:10]}"
