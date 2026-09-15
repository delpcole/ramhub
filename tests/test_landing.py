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


# -- Rambo -------------------------------------------------------------------
@pytest.mark.django_db
def test_rambo_section_renders_as_an_accessible_button(client):
    body = client.get("/").content
    assert b'data-rambo aria-label="Say hi to Rambo, the RamHub mascot"' in body
    assert b"<button" in body
    assert b"Meet" in body and b"Rambo." in body


@pytest.mark.django_db
def test_rambo_is_labelled_as_original_artwork(client):
    """The roadmap: an original character, not the college's official mark."""
    assert b"not an official college mark" in client.get("/").content


@pytest.mark.django_db
def test_rambo_lines_are_embedded_as_safe_json(client, make_course):
    make_course(code="CSC 229", title="Data Structures & Algorithms I")

    body = client.get("/").content.decode()

    assert 'id="rambo-lines"' in body
    assert (
        "Hi, I&#x27;m Rambo." in body or "Hi, I\\u0027m Rambo." in body or "Hi, I'm Rambo." in body
    )


@pytest.mark.django_db
def test_rambo_only_says_things_the_database_backs_up(make_course):
    from apps.catalog.services import rambo_lines

    course = make_course(code="CSC 229", title="Data Structures & Algorithms I")

    lines = rambo_lines(course_count=1785, department_count=67, featured_course=course)

    assert lines[0] == "Hi, I'm Rambo."
    assert any("1,785 courses" in line for line in lines)
    assert any("67 departments" in line for line in lines)
    assert any("CSC 229" in line for line in lines)
    # the assistant is not built, and Rambo must not imply that it is
    assert any("soon" in line for line in lines)


def test_rambo_lines_cope_with_an_empty_catalog():
    from apps.catalog.services import rambo_lines

    lines = rambo_lines(course_count=0, department_count=0, featured_course=None)

    assert lines and not any("None" in line for line in lines)


def test_the_old_mascot_name_is_gone_everywhere():
    root = Path(__file__).resolve().parent.parent
    offenders = [
        str(path.relative_to(root))
        for folder in ("templates", "apps", "static/js", "static/src", "config")
        for path in (root / folder).rglob("*")
        if path.is_file()
        and path.suffix in {".html", ".py", ".js", ".css"}
        and "rammy" in path.read_text(errors="ignore").lower()
    ]
    assert not offenders, offenders


@pytest.mark.django_db
def test_interactive_scripts_load_only_on_the_landing_page(client):
    assert b"js/cursor.js" in client.get("/").content
    assert b"js/rambo.js" in client.get("/").content
    for url in ("/courses/", "/professors/", "/feed/"):
        body = client.get(url).content
        assert b"cursor.js" not in body and b"rambo.js" not in body, url
