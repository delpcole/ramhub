from django.urls import path

from . import views

app_name = "campus"

urlpatterns = [
    path("clubs/", views.clubs, name="clubs"),
    path("jobs/", views.jobs, name="jobs"),
    path("parking/", views.parking, name="parking"),
    path("facilities/", views.facilities, name="facilities"),
]
