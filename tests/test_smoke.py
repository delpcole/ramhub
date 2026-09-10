"""
Smoke tests: the shell renders and the navigation works.

These prove routing, templates, and the active-tab rule rather than any model
behaviour — catalog behaviour is covered in apps/catalog/tests/. They do need
``django_db`` now: as of Phase 1 the Courses and Professors pages query on
every request, so rendering them touches MongoDB.
"""

import pytest
from django.urls import reverse

# Every page the nav or footer links to.
PAGE_URL_NAMES = [
    "community:feed",
    "catalog:courses",
    "catalog:professors",
    "campus:clubs",
    "campus:jobs",
    "campus:parking",
    "campus:facilities",
    "styleguide",
    "about",
    "guidelines",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", PAGE_URL_NAMES)
def test_page_renders(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 200


@pytest.mark.django_db
def test_nav_marks_only_the_current_tab_active(client):
    response = client.get(reverse("catalog:courses"))
    tabs = {tab["label"]: tab["is_active"] for tab in response.context["nav_tabs"]}
    assert tabs["Courses"] is True
    assert sum(tabs.values()) == 1


@pytest.mark.django_db
def test_feed_tab_is_not_active_on_other_pages(client):
    """The feed lives at "/", so a naive startswith check would always match."""
    response = client.get(reverse("campus:parking"))
    tabs = {tab["label"]: tab["is_active"] for tab in response.context["nav_tabs"]}
    assert tabs["Feed"] is False
    assert tabs["Parking"] is True


def test_base_template_sends_csrf_token_with_htmx_requests(client):
    response = client.get(reverse("community:feed"))
    assert b"hx-headers" in response.content
    assert b"X-CSRFToken" in response.content


def test_htmx_demo_returns_a_fragment_not_a_full_page(client):
    response = client.get(reverse("styleguide_htmx_demo"))
    assert response.status_code == 200
    assert b"<html" not in response.content
    assert b"Swapped from the server" in response.content
