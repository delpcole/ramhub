"""The landing page: real data, honest attribution, and motion kept to this page."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@pytest.mark.django_db
def test_landing_is_the_front_door(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.templates[0].name == "pages/home.html"


@pytest.mark.django_db
def test_feed_moved_off_the_root(client):
    assert reverse("community:feed") == "/feed/"
    assert client.get("/feed/").status_code == 200


@pytest.mark.django_db
def test_landing_shows_real_counts_not_marketing_numbers(client, make_course, make_professor):
    make_course(code="CSC 229", title="Data Structures & Algorithms I")
    make_course(code="MTH 150", title="Calculus I", department="Mathematics")
    make_professor(first_name="Ada", last_name="Lovelace")

    response = client.get("/")

    assert response.context["course_count"] == 2
    assert response.context["professor_count"] == 1
    assert b'data-count="2"' in response.content
    assert b"Data Structures &amp; Algorithms I" in response.content


@pytest.mark.django_db
def test_featured_professor_rating_is_attributed_to_rmp(client, make_professor):
    """CLAUDE.md: anywhere an RMP number appears, it must say where it came from."""
    from apps.catalog.models import ProfessorRatingSummary

    make_professor(
        first_name="Karen",
        last_name="Bottalico",
        rating_summary=ProfessorRatingSummary(
            avg_overall=4.9, count=226, source="rmp", rank_score=4.85
        ),
    )

    response = client.get("/")

    assert b"Karen Bottalico" in response.content
    assert b"ratings on Rate My Professors" in response.content


@pytest.mark.django_db
def test_landing_renders_with_an_empty_database(client):
    """A fresh clone before seed_demo must not crash the front door."""
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_motion_libraries_load_only_on_the_landing_page(client):
    """The directories stay on htmx + vanilla JS (CLAUDE.md)."""
    assert b"gsap.min.js" in client.get("/").content
    for url in ("/courses/", "/professors/", "/feed/"):
        body = client.get(url).content
        assert b"gsap" not in body and b"lenis" not in body, url


@pytest.mark.django_db
def test_hero_content_is_in_the_html_without_javascript(client):
    """Motion is an enhancement: the words must be there before any script runs."""
    body = client.get("/").content
    assert b"Know the class" in body
    assert b"before you take it." in body


def test_no_template_uses_a_multiline_hash_comment():
    """
    Django's {# #} comment is single-line only. Spread over several lines it
    renders as visible text — this shipped briefly into the nav during the
    landing page work. Use {% comment %} for anything longer than a line.
    """
    offenders = [
        f"{path.relative_to(TEMPLATES)}:{number}"
        for path in TEMPLATES.rglob("*.html")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if "{#" in line and "#}" not in line
    ]
    assert not offenders, offenders


def test_landing_css_is_scoped_so_it_cannot_leak_into_directories():
    css = (Path(__file__).resolve().parent.parent / "static/src/input.css").read_text()
    landing = css[css.index("Landing page\n") :]
    selectors = re.findall(r"^\s{2}(\.[a-z][\w-]*)", landing, flags=re.M)
    assert selectors, "expected landing selectors"
    # every landing component is namespaced to landing-only class names
    generic = [s for s in selectors if s in {".card", ".row-link", ".btn-primary", ".badge"}]
    assert not generic, generic
