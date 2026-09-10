from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("courses/", views.courses, name="courses"),
    # Course codes are the natural key, so they are the URL: /courses/CSC-240/.
    path("courses/<str:code>/", views.course_detail, name="course_detail"),
    path("professors/", views.professors, name="professors"),
    # The directory's own slug, not the ObjectId: it is stable across re-imports,
    # readable, and shareable. A malformed slug 404s at the routing layer.
    path("professors/<slug:slug>/", views.professor_detail, name="professor_detail"),
]
