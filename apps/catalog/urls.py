from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("courses/", views.courses, name="courses"),
    # Course codes are the natural key, so they are the URL: /courses/CSC-240/.
    path("courses/<str:code>/", views.course_detail, name="course_detail"),
    path("professors/", views.professors, name="professors"),
    # `object_id` is registered by django_mongodb_backend; a malformed id 404s
    # at the routing layer instead of blowing up in the view.
    path("professors/<object_id:pk>/", views.professor_detail, name="professor_detail"),
]
