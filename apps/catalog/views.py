from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def courses(request: HttpRequest) -> HttpResponse:
    """Directory of every course. Seeded from the catalog in Phase 1."""
    return render(request, "catalog/courses.html")


def professors(request: HttpRequest) -> HttpResponse:
    """Directory of every instructor. Seeded from the faculty list in Phase 1."""
    return render(request, "catalog/professors.html")
