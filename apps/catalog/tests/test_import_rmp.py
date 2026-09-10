"""
The RMP import is the one place RamHub writes ratings it did not receive from
its own students. These tests pin the conditions that make that acceptable:
the numbers are tagged as RMP's, they never overwrite a student rating, and
absence is never rendered as a zero.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.management.commands.import_rmp import normalize_name
from apps.catalog.models import Professor, ProfessorRatingSummary

pytestmark = pytest.mark.django_db


def rmp(first, last, **extra):
    base = {
        "firstName": first,
        "lastName": last,
        "department": "Psychology",
        "legacyId": 351387,
        "avgRating": 4.9,
        "avgDifficulty": 1.8,
        "numRatings": 226,
        "wouldTakeAgainPercent": 98.7,
        "courseCodes": [],
    }
    base.update(extra)
    return base


@pytest.fixture
def rmp_file(tmp_path):
    def _write(rows):
        path = tmp_path / "rmp.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return str(path)

    return _write


def run_import(path, *args) -> str:
    out = StringIO()
    call_command("import_rmp", "--file", path, *args, stdout=out)
    return out.getvalue()


# -- matching --------------------------------------------------------------
def test_matches_and_writes_rmp_fields(make_professor, rmp_file):
    professor = make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    professor.refresh_from_db()
    assert professor.rmp_legacy_id == 351387
    assert professor.rmp_avg_rating == 4.9
    assert professor.rmp_avg_difficulty == 1.8
    assert professor.rmp_would_take_again_pct == 98.7
    assert professor.rmp_num_ratings == 226
    assert professor.has_rmp_profile is True


@pytest.mark.parametrize(
    "first,last",
    [("karen", "bottalico"), ("KAREN", "BOTTALICO"), ("Dr. Karen", "Bottalico")],
)
def test_matching_ignores_case_and_titles(make_professor, rmp_file, first, last):
    make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp(first, last)]))

    assert Professor.objects.get(slug="karen-bottalico").rmp_legacy_id == 351387


def test_name_normalisation_folds_accents():
    assert normalize_name("José", "O'Brien") == ("jose", "o brien")
    assert normalize_name("Dr. Ada", "Lovelace") == ("ada", "lovelace")


def test_unmatched_professors_are_left_alone(make_professor, rmp_file):
    professor = make_professor(first_name="Nobody", last_name="Here")

    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    professor.refresh_from_db()
    assert professor.rmp_legacy_id is None
    assert professor.rating_summary.count == 0
    assert professor.has_rmp_profile is False


def test_duplicate_rmp_profiles_resolve_to_the_most_rated(make_professor, rmp_file):
    """Students sometimes create a second profile instead of finding the first."""
    make_professor(first_name="Cliff", last_name="Miller")

    run_import(
        rmp_file(
            [
                rmp("Cliff", "Miller", legacyId=1978902, numRatings=20, avgRating=4.9),
                rmp("Cliff", "Miller", legacyId=2716355, numRatings=0, avgRating=0),
            ]
        )
    )

    assert Professor.objects.get(slug="cliff-miller").rmp_legacy_id == 1978902


# -- provenance ------------------------------------------------------------
def test_imported_ratings_are_tagged_as_rmp(make_professor, rmp_file):
    """Without the tag the UI cannot tell an import from a student review."""
    make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    summary = Professor.objects.get(slug="karen-bottalico").rating_summary
    assert summary.source == ProfessorRatingSummary.SOURCE_RMP
    assert summary.is_from_rmp is True
    assert summary.avg_overall == 4.9
    assert summary.count == 226


def test_rmp_has_no_clarity_helpfulness_or_fairness(make_professor, rmp_file):
    """One quality score must not be split into three invented sub-scores."""
    make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    summary = Professor.objects.get(slug="karen-bottalico").rating_summary
    assert summary.avg_clarity is None
    assert summary.avg_helpfulness is None
    assert summary.avg_fairness is None


def test_student_ratings_are_never_overwritten(make_professor, rmp_file):
    """A rating left on RamHub outranks an imported aggregate, always."""
    make_professor(
        first_name="Karen",
        last_name="Bottalico",
        clarity=3.0,
        helpfulness=3.0,
        fairness=3.0,
        count=4,
    )

    output = run_import(rmp_file([rmp("Karen", "Bottalico")]))

    summary = Professor.objects.get(slug="karen-bottalico").rating_summary
    assert summary.source == ProfessorRatingSummary.SOURCE_RAMHUB
    assert summary.count == 4
    assert "Protected" in output


# -- absence is not a zero -------------------------------------------------
def test_unrated_rmp_records_store_no_scores(make_professor, rmp_file):
    """RMP sends 0 for an unrated professor; that is absence, not a 0/5."""
    make_professor(first_name="New", last_name="Hire")

    run_import(
        rmp_file(
            [
                rmp(
                    "New",
                    "Hire",
                    numRatings=0,
                    avgRating=0,
                    avgDifficulty=0,
                    wouldTakeAgainPercent=-1,
                )
            ]
        )
    )

    professor = Professor.objects.get(slug="new-hire")
    assert professor.rmp_avg_rating is None
    assert professor.rmp_avg_difficulty is None
    assert professor.rmp_would_take_again_pct is None
    assert professor.rating_summary.count == 0
    # but the id is still useful for a direct link
    assert professor.has_rmp_profile is True


def test_missing_would_take_again_is_null_not_negative(make_professor, rmp_file):
    make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp("Karen", "Bottalico", wouldTakeAgainPercent=-1)]))

    assert Professor.objects.get(slug="karen-bottalico").rmp_would_take_again_pct is None


# -- ranking ---------------------------------------------------------------
def test_rank_score_is_written_so_the_directory_can_sort(make_professor, rmp_file):
    make_professor(first_name="Karen", last_name="Bottalico")

    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    summary = Professor.objects.get(slug="karen-bottalico").rating_summary
    assert summary.rank_score is not None
    assert summary.rank_score < summary.avg_overall  # pulled toward the prior


# -- lifecycle -------------------------------------------------------------
def test_import_is_idempotent(make_professor, rmp_file):
    make_professor(first_name="Karen", last_name="Bottalico")
    path = rmp_file([rmp("Karen", "Bottalico")])

    run_import(path)
    run_import(path)

    assert Professor.objects.get(slug="karen-bottalico").rating_summary.count == 226


def test_clear_removes_rmp_data_and_its_ratings(make_professor, rmp_file):
    make_professor(first_name="Karen", last_name="Bottalico")
    run_import(rmp_file([rmp("Karen", "Bottalico")]))

    call_command("import_rmp", "--clear", stdout=StringIO())

    professor = Professor.objects.get(slug="karen-bottalico")
    assert professor.rmp_legacy_id is None
    assert professor.rating_summary.count == 0
    assert professor.rating_summary.source == ""


def test_missing_file_is_a_clean_error():
    with pytest.raises(CommandError, match="not found"):
        run_import("/tmp/no-such-rmp.json")


def test_bad_retrieved_date_is_a_clean_error(make_professor, rmp_file):
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        run_import(rmp_file([rmp("Karen", "Bottalico")]), "--retrieved", "yesterday")


# -- the shipped export ----------------------------------------------------
def test_the_bundled_rmp_export_is_usable():
    from apps.catalog.management.commands.import_rmp import DATA_FILE

    assert DATA_FILE.exists(), "the RMP export should be committed"
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    assert len(rows) > 1500
    assert all(r.get("legacyId") for r in rows)
    rated = [r for r in rows if (r.get("numRatings") or 0) > 0]
    assert len(rated) > 1000
