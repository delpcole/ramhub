from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("feed/", views.feed, name="feed"),
]
