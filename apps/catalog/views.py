"""
Catalog pages. Views parse the request, call a service, and render.

The directories are built plain-GET first and progressively enhanced: with
JavaScript off the search box and filters are an ordinary form submit and
"Load more" is a link. HTMX layers partial swaps on top by re-rendering the same
partials the full page is assembled from.

These pages are public for now. Phase 2 puts them behind the college-email gate.
"""

from urllib.parse import urlencode

from django.core.paginator import Page, Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import services
from .forms import CourseDirectoryForm, DirectoryQuery, ProfessorDirectoryForm
from .models import Professor
from .services import COURSE_SORTS, PAGE_SIZE, PROFESSOR_SORTS


def _page_url(query: DirectoryQuery, page_number: int) -> str:
    """Query string for the next page, preserving the current search and filters."""
    params = {"page": page_number, "append": 1}
    if query.q:
        params["q"] = query.q
    if query.department:
        params["department"] = query.department
    if query.sort:
        params["sort"] = query.sort
    return "?" + urlencode(params)


def _directory_context(
    query: DirectoryQuery, page: Page, departments: list[str], sorts, clear_url: str
) -> dict:
    return {
        "query": query,
        "page_obj": page,
        "total": page.paginator.count,
        "departments": departments,
        "sorts": sorts,
        "next_page_url": (_page_url(query, page.next_page_number()) if page.has_next() else None),
        "is_filtered": bool(query.q or query.department),
        # Where the empty state's "clear" button goes — the unfiltered directory.
        "clear_url": clear_url,
    }


def _render_directory(
    request: HttpRequest, query: DirectoryQuery, context: dict, templates: dict[str, str]
) -> HttpResponse:
    """
    Pick the right slice of the page for the request.

    append  -> just the next rows, swapped in after the current ones
    HTMX    -> the whole results region (a new search or sort)
    plain   -> the full page
    """
    if request.headers.get("HX-Request"):
        name = templates["rows"] if query.append else templates["results"]
    else:
        name = templates["page"]
    return render(request, name, context)


def courses(request: HttpRequest) -> HttpResponse:
    """The course directory: search, filter by department, sort, paginate."""
    departments = services.course_departments()
    form = CourseDirectoryForm(request.GET, departments=departments)
    query = form.to_query()

    results = services.search_courses(q=query.q, department=query.department, sort=query.sort)
    page = Paginator(results, PAGE_SIZE).get_page(query.page)

    context = _directory_context(query, page, departments, COURSE_SORTS, reverse("catalog:courses"))
    context["form"] = form
    return _render_directory(
        request,
        query,
        context,
        {
            "page": "catalog/courses.html",
            "results": "catalog/partials/course_results.html",
            "rows": "catalog/partials/course_rows.html",
        },
    )


def professors(request: HttpRequest) -> HttpResponse:
    """The professor directory: search by name, filter by department, sort, paginate."""
    departments = services.professor_departments()
    form = ProfessorDirectoryForm(request.GET, departments=departments)
    query = form.to_query()

    results = services.search_professors(q=query.q, department=query.department, sort=query.sort)
    page = Paginator(results, PAGE_SIZE).get_page(query.page)

    context = _directory_context(
        query, page, departments, PROFESSOR_SORTS, reverse("catalog:professors")
    )
    context["form"] = form
    return _render_directory(
        request,
        query,
        context,
        {
            "page": "catalog/professors.html",
            "results": "catalog/partials/professor_results.html",
            "rows": "catalog/partials/professor_rows.html",
        },
    )


def course_detail(request: HttpRequest, code: str) -> HttpResponse:
    """One course. `code` arrives URL-shaped, e.g. CSC-240."""
    course = services.get_course_by_code(code)
    if course is None:
        raise Http404(f"No course with code {code!r}")
    return render(
        request,
        "catalog/course_detail.html",
        {"course": course, "professors": services.professors_for_course(course)},
    )


def professor_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """One professor, keyed on the directory slug."""
    professor = get_object_or_404(Professor, slug=slug)
    return render(
        request,
        "catalog/professor_detail.html",
        {"professor": professor, "courses": services.courses_for_professor(professor)},
    )
