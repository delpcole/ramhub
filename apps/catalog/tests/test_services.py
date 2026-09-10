"""Directory search, filtering, sorting, and the two-way Course <-> Professor link."""

import pytest

from apps.catalog import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(make_course, make_professor):
    """A small, deliberately ordered catalog: one easy, one hard, one unrated."""
    return {
        "easy": make_course(
            code="BUS 101",
            title="Introduction to Business",
            department="Business",
            difficulty=1.7,
            workload=2.1,
            usefulness=4.8,
            count=62,
        ),
        "hard": make_course(
            code="CSC 240",
            title="Data Structures",
            department="Computer Science",
            difficulty=4.6,
            workload=4.5,
            usefulness=4.3,
            count=40,
        ),
        "middling": make_course(
            code="CSC 111",
            title="Introduction to Programming",
            department="Computer Science",
            difficulty=3.0,
            workload=3.1,
            usefulness=4.0,
            count=80,
        ),
        "unrated": make_course(
            code="CSC 440",
            title="Computer Networks",
            department="Computer Science",
        ),
    }


# -- search ----------------------------------------------------------------
def test_search_matches_a_course_code(catalog):
    assert [c.code for c in services.search_courses(q="CSC 240")] == ["CSC 240"]


def test_search_matches_a_title(catalog):
    assert [c.code for c in services.search_courses(q="data structures")] == ["CSC 240"]


def test_search_is_case_insensitive(catalog):
    assert [c.code for c in services.search_courses(q="DATA STRUCTURES")] == ["CSC 240"]


@pytest.mark.parametrize("term", ["csc240", "csc-240", "CSC240", "csc 240"])
def test_search_normalises_course_code_shapes(catalog, term):
    """ "csc240" and "csc-240" have to find "CSC 240"."""
    assert [c.code for c in services.search_courses(q=term)] == ["CSC 240"]


def test_search_with_no_matches_returns_nothing(catalog):
    assert services.search_courses(q="zzzznomatch").count() == 0


def test_department_filter(catalog):
    codes = {c.code for c in services.search_courses(department="Computer Science")}
    assert codes == {"CSC 111", "CSC 240", "CSC 440"}


def test_search_and_department_filter_combine(catalog):
    results = services.search_courses(q="Introduction", department="Computer Science")
    assert [c.code for c in results] == ["CSC 111"]


# -- sorting ---------------------------------------------------------------
def test_sort_by_code_is_the_default(catalog):
    assert [c.code for c in services.search_courses()] == [
        "BUS 101",
        "CSC 111",
        "CSC 240",
        "CSC 440",
    ]


def test_sort_hardest_first(catalog):
    assert [c.code for c in services.search_courses(sort="hardest")][:3] == [
        "CSC 240",
        "CSC 111",
        "BUS 101",
    ]


def test_sort_easiest_first(catalog):
    assert [c.code for c in services.search_courses(sort="easiest")][:3] == [
        "BUS 101",
        "CSC 111",
        "CSC 240",
    ]


def test_unrated_courses_sort_last_not_first(catalog):
    """Without nulls_last the unrated course would lead the "easiest" list."""
    assert [c.code for c in services.search_courses(sort="easiest")][-1] == "CSC 440"
    assert [c.code for c in services.search_courses(sort="hardest")][-1] == "CSC 440"


def test_sort_most_useful(catalog):
    assert [c.code for c in services.search_courses(sort="useful")][0] == "BUS 101"


def test_sort_most_rated(catalog):
    """Rating counts are 80, 62, 40, 0."""
    assert [c.code for c in services.search_courses(sort="reviews")] == [
        "CSC 111",
        "BUS 101",
        "CSC 240",
        "CSC 440",
    ]


def test_unknown_sort_key_falls_back_to_the_default(catalog):
    assert [c.code for c in services.search_courses(sort="nonsense")] == [
        c.code for c in services.search_courses(sort="code")
    ]


# -- professors ------------------------------------------------------------
@pytest.fixture
def faculty(make_professor):
    return {
        "reyes": make_professor(
            first_name="Marisol",
            last_name="Reyes",
            department="Computer Science",
            clarity=4.5,
            helpfulness=4.2,
            fairness=4.0,
            count=63,
        ),
        "zhang": make_professor(
            first_name="Wei",
            last_name="Zhang",
            department="Mathematics",
            clarity=3.1,
            helpfulness=3.0,
            fairness=3.2,
            count=90,
        ),
        "doyle": make_professor(
            first_name="Colleen",
            last_name="Doyle",
            department="English",
        ),
    }


@pytest.mark.parametrize("term", ["reyes", "Reyes", "marisol", "marisol reyes", "Reyes Marisol"])
def test_professor_search_matches_either_name_in_any_order(faculty, term):
    assert [p.last_name for p in services.search_professors(q=term)] == ["Reyes"]


def test_professor_department_filter(faculty):
    assert [p.last_name for p in services.search_professors(department="Mathematics")] == ["Zhang"]


def test_professor_sort_by_name_is_the_default(faculty):
    assert [p.last_name for p in services.search_professors()] == ["Doyle", "Reyes", "Zhang"]


def test_professor_sort_by_rating_puts_unrated_last(faculty):
    assert [p.last_name for p in services.search_professors(sort="rating")] == [
        "Reyes",
        "Zhang",
        "Doyle",
    ]


def test_professor_sort_by_reviews(faculty):
    assert [p.last_name for p in services.search_professors(sort="reviews")][0] == "Zhang"


# -- departments -----------------------------------------------------------
def test_course_departments_are_deduplicated(catalog):
    """Meta.ordering silently breaks .distinct() unless order_by is set first."""
    assert services.course_departments() == ["Business", "Computer Science"]


def test_professor_departments_are_deduplicated(faculty):
    assert services.professor_departments() == ["Computer Science", "English", "Mathematics"]


# -- lookups and the two-way link -----------------------------------------
def test_get_course_by_code_accepts_the_url_form(catalog):
    assert services.get_course_by_code("CSC-240").code == "CSC 240"


def test_get_course_by_code_is_case_insensitive(catalog):
    assert services.get_course_by_code("csc-240").code == "CSC 240"


def test_get_course_by_code_returns_none_when_missing(catalog):
    assert services.get_course_by_code("NOPE-999") is None


def test_link_writes_both_sides(catalog, faculty):
    course, professor = catalog["hard"], faculty["reyes"]

    services.link_course_and_professor(course, professor)

    assert professor.pk in services.get_course_by_code("CSC-240").professor_ids
    assert course.pk in type(professor).objects.get(pk=professor.pk).course_ids


def test_link_is_idempotent(catalog, faculty):
    course, professor = catalog["hard"], faculty["reyes"]

    services.link_course_and_professor(course, professor)
    services.link_course_and_professor(course, professor)

    assert services.get_course_by_code("CSC-240").professor_ids == [professor.pk]


def test_professors_for_course_resolves_the_id_array(catalog, faculty):
    services.link_course_and_professor(catalog["hard"], faculty["reyes"])

    found = services.professors_for_course(catalog["hard"])

    assert [p.full_name for p in found] == ["Marisol Reyes"]


def test_courses_for_professor_resolves_the_reverse(catalog, faculty):
    services.link_course_and_professor(catalog["hard"], faculty["reyes"])
    services.link_course_and_professor(catalog["middling"], faculty["reyes"])

    found = services.courses_for_professor(faculty["reyes"])

    assert [c.code for c in found] == ["CSC 111", "CSC 240"]


def test_resolution_is_empty_when_nothing_is_linked(catalog, faculty):
    assert services.professors_for_course(catalog["unrated"]) == []
    assert services.courses_for_professor(faculty["doyle"]) == []
