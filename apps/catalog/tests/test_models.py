"""Model behaviour that only a real MongoDB round-trip can prove."""

import pytest
from bson import ObjectId
from django.db import IntegrityError

from apps.catalog.models import Course, CourseRatingSummary, ProfessorRatingSummary

pytestmark = pytest.mark.django_db


def test_course_round_trips_with_an_objectid_pk(make_course):
    course = make_course(code="CSC 240", title="Data Structures", credits=4)

    stored = Course.objects.get(code="CSC 240")

    assert isinstance(stored.pk, ObjectId)
    assert stored.pk == course.pk
    assert stored.title == "Data Structures"
    assert stored.credits == 4


def test_rating_summary_round_trips_as_an_embedded_document(make_course):
    make_course(code="CSC 240", difficulty=4.1, workload=4.5, usefulness=4.3, count=40)

    summary = Course.objects.get(code="CSC 240").rating_summary

    assert isinstance(summary, CourseRatingSummary)
    assert (summary.avg_difficulty, summary.avg_workload, summary.avg_usefulness) == (4.1, 4.5, 4.3)
    assert summary.count == 40
    assert summary.has_ratings is True


def test_unrated_course_has_a_summary_with_zero_count_not_a_missing_one(make_course):
    """The "nobody has rated this" state is count=0 and null averages."""
    make_course(code="CSC 440")

    summary = Course.objects.get(code="CSC 440").rating_summary

    assert summary is not None
    assert summary.count == 0
    assert summary.avg_difficulty is None
    assert summary.has_ratings is False


def test_duplicate_course_code_is_rejected(make_course):
    make_course(code="CSC 240")

    with pytest.raises(IntegrityError):
        make_course(code="CSC 240", title="A different course")


def test_course_codes_differing_only_by_case_are_distinct_documents(make_course):
    """The unique index is exact; get_course_by_code() is what normalises case."""
    make_course(code="CSC 240")
    make_course(code="csc 240", title="Lowercase")

    assert Course.objects.count() == 2


def test_professor_overall_is_the_mean_of_known_axes():
    assert ProfessorRatingSummary.compute_overall(4.0, 5.0, 3.0) == 4.0
    assert ProfessorRatingSummary.compute_overall(4.0, None, 3.0) == 3.5
    assert ProfessorRatingSummary.compute_overall(None, None, None) is None


def test_course_slug_is_the_url_form_of_the_code(make_course):
    assert make_course(code="CSC 240").slug == "CSC-240"


def test_professor_ids_store_and_return_objectids(make_course, make_professor):
    course = make_course(code="CSC 240")
    professor = make_professor(last_name="Reyes")

    course.professor_ids = [professor.pk]
    course.save()

    stored = Course.objects.get(pk=course.pk)
    assert len(stored.professor_ids) == 1
    assert isinstance(stored.professor_ids[0], ObjectId)
    assert stored.professor_ids[0] == professor.pk


def test_rmp_link_is_a_farmingdale_scoped_search(make_professor):
    """
    A search, not a deep link: the directory has no RMP ids, and RMP holds
    duplicate entries per person. Guessing an id would land students on the
    wrong professor.
    """
    professor = make_professor(first_name="Melixa", last_name="Abad Izquierdo")

    url = professor.rmp_search_url

    assert url.startswith("https://www.ratemyprofessors.com/search/professors/14046?q=")
    assert "Melixa+Abad+Izquierdo" in url


def test_rmp_link_url_encodes_awkward_names(make_professor):
    professor = make_professor(first_name="José", last_name="O'Brien-Smith")

    url = professor.rmp_search_url

    assert " " not in url
    assert "'" not in url
