"""
Site-level pages that do not belong to a product app.

Kept here deliberately so INSTALLED_APPS matches the layout in CLAUDE.md
exactly — no extra "core"/"pages" app.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone


def styleguide(request: HttpRequest) -> HttpResponse:
    """Every shared UI pattern on one page. Review the visual system here."""
    return render(request, "pages/styleguide.html")


def styleguide_htmx_demo(request: HttpRequest) -> HttpResponse:
    """
    Target of the style guide's HTMX demo.

    Returns an HTML fragment (not JSON) — that is the HTMX contract used
    everywhere in this project for partial page updates.
    """
    return render(
        request,
        "partials/htmx_demo_result.html",
        {"loaded_at": timezone.localtime()},
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/about.html")


def guidelines(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/guidelines.html")
