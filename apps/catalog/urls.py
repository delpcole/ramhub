from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("courses/", views.courses, name="courses"),
    path("professors/", views.professors, name="professors"),
]
