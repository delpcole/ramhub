from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def feed(request: HttpRequest) -> HttpResponse:
    """Campus-wide community feed. Posts arrive in Phase 3."""
    return render(request, "community/feed.html")
