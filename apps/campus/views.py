from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def clubs(request: HttpRequest) -> HttpResponse:
    return render(request, "campus/clubs.html")


def jobs(request: HttpRequest) -> HttpResponse:
    return render(request, "campus/jobs.html")


def parking(request: HttpRequest) -> HttpResponse:
    return render(request, "campus/parking.html")


def facilities(request: HttpRequest) -> HttpResponse:
    return render(request, "campus/facilities.html")
