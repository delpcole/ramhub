"""Template context shared by every page."""

from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse

# The primary navigation, in display order. Adding a tab here adds it to the
# desktop nav and the mobile menu — the templates iterate this list.
NAV_TABS: list[dict[str, str]] = [
    {"label": "Feed", "url_name": "community:feed", "icon": "chat"},
    {"label": "Courses", "url_name": "catalog:courses", "icon": "book"},
    {"label": "Professors", "url_name": "catalog:professors", "icon": "users"},
    {"label": "Clubs", "url_name": "campus:clubs", "icon": "flag"},
    {"label": "Jobs", "url_name": "campus:jobs", "icon": "briefcase"},
    {"label": "Parking", "url_name": "campus:parking", "icon": "car"},
    {"label": "Facilities", "url_name": "campus:facilities", "icon": "building"},
]


def navigation(request: HttpRequest) -> dict[str, object]:
    """
    Build the nav tabs with an ``is_active`` flag derived from the current URL.

    Kept out of the templates (and out of every view) so the active-tab rule
    lives in exactly one place. ``startswith`` means a future detail page such
    as /courses/CSC-240/ keeps the Courses tab lit; the feed lives at "/" so it
    has to match exactly or it would light up on every page.
    """
    tabs = []
    for tab in NAV_TABS:
        try:
            url = reverse(tab["url_name"])
        except NoReverseMatch:  # pragma: no cover - a tab pointing at a dead url
            continue
        tabs.append(
            {
                **tab,
                "url": url,
                "is_active": (request.path == url if url == "/" else request.path.startswith(url)),
            }
        )
    return {"nav_tabs": tabs}
