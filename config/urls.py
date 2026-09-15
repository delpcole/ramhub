"""RamHub URL configuration."""

from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # The feed is the front page.
    path("", views.home, name="home"),
    path("", include("apps.community.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.campus.urls")),
    # Site-level pages
    path("styleguide/", views.styleguide, name="styleguide"),
    path("styleguide/htmx-demo/", views.styleguide_htmx_demo, name="styleguide_htmx_demo"),
    path("about/", views.about, name="about"),
    path("guidelines/", views.guidelines, name="guidelines"),
]
