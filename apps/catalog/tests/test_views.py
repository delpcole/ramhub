"""The two directories and the two detail pages, including the HTMX paths."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(make_course, make_professor):
    course = make_course(
        code="CSC 240",
        title="Data Structures",
        department="Computer Science",
        credits=4,
        difficulty=4.6,
        workload=4.5,
        usefulness=4.3,
        count=40,
    )
    professor = make_professor(
        first_name="Marisol",
        last_name="Reyes",
        department="Computer Science",
        clarity=4.5,
        helpfulness=4.2,
        fairness=4.0,
        count=63,
    )
    course.professor_ids = [professor.pk]
    course.save()
    professor.course_ids = [course.pk]
    professor.save()
    return course, professor


# -- directories -----------------------------------------------------------
def test_courses_directory_lists_a_seeded_course(client, catalog):
    response = client.get(reverse("catalog:courses"))

    assert response.status_code == 200
    assert b"CSC 240" in response.content
    assert b"Data Structures" in response.content


def test_professors_directory_lists_a_seeded_professor(client, catalog):
    response = client.get(reverse("catalog:professors"))

    assert response.status_code == 200
    assert b"Marisol Reyes" in response.content


def test_directory_search_narrows_the_results(client, catalog, make_course):
    make_course(code="BIO 120", title="General Biology I", department="Biology")

    response = client.get(reverse("catalog:courses"), {"q": "biology"})

    # Assert on the result set, not the page bytes: "CSC 240" also appears in
    # the search box's placeholder text.
    assert [c.code for c in response.context["page_obj"]] == ["BIO 120"]
    assert b"General Biology I" in response.content


def test_search_with_no_matches_renders_the_empty_state(client, catalog):
    response = client.get(reverse("catalog:courses"), {"q": "zzzznomatch"})

    assert response.status_code == 200
    assert b"No courses match that search" in response.content
    # and offers a way back to the full list
    assert reverse("catalog:courses").encode() in response.content


def test_professor_search_with_no_matches_renders_the_empty_state(client, catalog):
    response = client.get(reverse("catalog:professors"), {"q": "zzzznomatch"})

    assert b"No professors match that search" in response.content


def test_department_filter_is_applied(client, catalog, make_course):
    make_course(code="BIO 120", title="General Biology I", department="Biology")

    response = client.get(reverse("catalog:courses"), {"department": "Biology"})

    assert [c.code for c in response.context["page_obj"]] == ["BIO 120"]


def test_departments_that_do_not_exist_are_ignored_rather_than_erroring(client, catalog):
    """A stale bookmark should show the full directory, not a 400."""
    response = client.get(reverse("catalog:courses"), {"department": "Astrology"})

    assert response.status_code == 200
    assert [c.code for c in response.context["page_obj"]] == ["CSC 240"]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "nonsense"},
        {"page": "abc"},
        {"page": "-5"},
        {"q": "x" * 500},
    ],
)
def test_bad_query_parameters_degrade_instead_of_failing(client, catalog, params):
    assert client.get(reverse("catalog:courses"), params).status_code == 200


# -- HTMX ------------------------------------------------------------------
def test_htmx_search_returns_only_the_results_region(client, catalog):
    response = client.get(reverse("catalog:courses"), {"q": "data"}, headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert b"<html" not in response.content
    assert b'id="course-results"' in response.content
    assert b"CSC 240" in response.content


def test_htmx_append_returns_only_rows(client, catalog):
    """ "Load more" must not send the results wrapper, or it would nest."""
    response = client.get(
        reverse("catalog:courses"),
        {"page": "1", "append": "1"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b'id="course-results"' not in response.content
    assert b"CSC 240" in response.content


def test_a_plain_request_still_returns_the_whole_page(client, catalog):
    """The directory has to work with JavaScript off."""
    response = client.get(reverse("catalog:courses"), {"q": "data"})

    assert b"<html" in response.content
    assert b'id="course-results"' in response.content


def test_pagination_splits_at_25(client, make_course):
    for i in range(30):
        make_course(code=f"TST {100 + i}", title=f"Course {i}")

    first = client.get(reverse("catalog:courses"))
    assert first.context["page_obj"].paginator.count == 30
    assert len(first.context["page_obj"].object_list) == 25
    assert first.context["next_page_url"] is not None

    second = client.get(reverse("catalog:courses"), {"page": "2"})
    assert len(second.context["page_obj"].object_list) == 5
    assert second.context["next_page_url"] is None


def test_next_page_url_keeps_the_current_search_and_sort(client, make_course):
    for i in range(30):
        make_course(code=f"TST {100 + i}", title=f"Biology {i}", department="Biology")

    response = client.get(reverse("catalog:courses"), {"q": "biology", "sort": "hardest"})

    next_url = response.context["next_page_url"]
    assert "q=biology" in next_url
    assert "sort=hardest" in next_url
    assert "page=2" in next_url


# -- detail pages ----------------------------------------------------------
def test_course_detail_renders_and_links_its_professors(client, catalog):
    course, professor = catalog

    response = client.get(reverse("catalog:course_detail", args=[course.slug]))

    assert response.status_code == 200
    assert b"Data Structures" in response.content
    assert b"Marisol Reyes" in response.content
    assert reverse("catalog:professor_detail", args=[professor.slug]).encode() in response.content


def test_professor_detail_renders_and_links_its_courses(client, catalog):
    course, professor = catalog

    response = client.get(reverse("catalog:professor_detail", args=[professor.slug]))

    assert response.status_code == 200
    assert b"Marisol Reyes" in response.content
    assert b"CSC 240" in response.content
    assert reverse("catalog:course_detail", args=[course.slug]).encode() in response.content


def test_unknown_course_code_404s(client, catalog):
    assert client.get("/courses/NOPE-999/").status_code == 404


def test_unknown_professor_slug_404s(client, catalog):
    assert client.get("/professors/nobody-at-all/").status_code == 404


def test_slug_shaped_like_an_objectid_still_404s(client, catalog):
    """Professor URLs moved from ObjectId to the directory slug in the import."""
    assert client.get("/professors/aaaaaaaaaaaaaaaaaaaaaaaa/").status_code == 404


def test_unrated_course_detail_says_so_rather_than_showing_zeros(client, make_course):
    make_course(code="CSC 440", title="Computer Networks")

    response = client.get(reverse("catalog:course_detail", args=["CSC-440"]))

    assert b"No one has rated this course yet." in response.content
    assert b"0.0" not in response.content


def test_course_detail_url_keeps_the_courses_tab_active(client, catalog):
    """The Phase 0 active-tab rule assumes this URL shape."""
    response = client.get(reverse("catalog:course_detail", args=["CSC-240"]))

    tabs = {t["label"]: t["is_active"] for t in response.context["nav_tabs"]}
    assert tabs["Courses"] is True
    assert sum(tabs.values()) == 1


def test_professor_detail_url_keeps_the_professors_tab_active(client, catalog):
    _, professor = catalog

    response = client.get(reverse("catalog:professor_detail", args=[professor.slug]))

    tabs = {t["label"]: t["is_active"] for t in response.context["nav_tabs"]}
    assert tabs["Professors"] is True
