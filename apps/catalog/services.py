"""
Catalog business logic. Views parse the request, call these, and render.

Two MongoDB rules shape everything here:

* The Course <-> Professor link is an ObjectId array on both sides, so it
  resolves with a single ``filter(pk__in=...)``. There is no ``$lookup`` and no
  ``prefetch_related`` (unsupported).
* Rating sorts read the denormalized ``rating_summary`` — never a live
  aggregation. Unrated records hold nulls, so every rating sort passes
  ``nulls_last=True`` or the six unrated courses would lead the "easiest" list.
"""

import re
from typing import NamedTuple

from django.db.models import F, Q, QuerySet

from .models import Course, Professor

PAGE_SIZE = 25

# "csc240", "csc-240", "CSC  240" all mean "CSC 240".
_COURSE_CODE_RE = re.compile(r"^([A-Za-z]{2,4})[\s\-]*(\d{2,4})$")


class SortSpec(NamedTuple):
    label: str
    order_by: list


COURSE_SORTS: dict[str, SortSpec] = {
    "code": SortSpec("Course code", [F("code").asc()]),
    "useful": SortSpec(
        "Most useful",
        [F("rating_summary__avg_usefulness").desc(nulls_last=True), F("code").asc()],
    ),
    "easiest": SortSpec(
        "Easiest first",
        [F("rating_summary__avg_difficulty").asc(nulls_last=True), F("code").asc()],
    ),
    "hardest": SortSpec(
        "Hardest first",
        [F("rating_summary__avg_difficulty").desc(nulls_last=True), F("code").asc()],
    ),
    "reviews": SortSpec("Most rated", [F("rating_summary__count").desc(), F("code").asc()]),
}

PROFESSOR_SORTS: dict[str, SortSpec] = {
    "name": SortSpec("Name (A–Z)", [F("last_name").asc(), F("first_name").asc()]),
    # Orders on rank_score, not the raw average — see
    # ProfessorRatingSummary.rank_score for why a 5.0 from one rating should not
    # outrank a 4.9 from 226.
    "rating": SortSpec(
        "Highest rated",
        [F("rating_summary__rank_score").desc(nulls_last=True), F("last_name").asc()],
    ),
    "reviews": SortSpec("Most reviewed", [F("rating_summary__count").desc(), F("last_name").asc()]),
}


# --------------------------------------------------------------------------
# Departments
# --------------------------------------------------------------------------
# The explicit .order_by("department") below is load-bearing, not decoration.
# Both models set Meta.ordering, and that default ordering gets folded into the
# DISTINCT grouping — so `.values_list("department").distinct()` on its own
# dedupes on (code, department) and silently returns one row per course. It
# returns 66 departments instead of 8, with no error. Clearing the ordering
# first is what makes distinct() mean what it looks like it means.
def course_departments() -> list[str]:
    return sorted(
        Course.objects.order_by("department").values_list("department", flat=True).distinct()
    )


def professor_departments() -> list[str]:
    return sorted(
        Professor.objects.order_by("department").values_list("department", flat=True).distinct()
    )


# --------------------------------------------------------------------------
# Directories
# --------------------------------------------------------------------------
def normalize_course_code(term: str) -> str | None:
    """Turn a code-shaped search term into catalog form, or None if it isn't one."""
    match = _COURSE_CODE_RE.match(term.strip())
    return f"{match.group(1).upper()} {match.group(2)}" if match else None


def search_courses(*, q: str = "", department: str = "", sort: str = "code") -> QuerySet[Course]:
    """Filter and order the course directory. Matches on code and title."""
    queryset = Course.objects.all()

    if department:
        queryset = queryset.filter(department=department)

    if q:
        criteria = Q(code__icontains=q) | Q(title__icontains=q)
        # So that "csc240" and "csc-240" find "CSC 240".
        if normalized := normalize_course_code(q):
            criteria |= Q(code__istartswith=normalized)
        queryset = queryset.filter(criteria)

    spec = COURSE_SORTS.get(sort) or COURSE_SORTS["code"]
    return queryset.order_by(*spec.order_by)


def search_professors(
    *, q: str = "", department: str = "", sort: str = "name"
) -> QuerySet[Professor]:
    """
    Filter and order the professor directory.

    Each whitespace-separated term must match a first or last name, so "reyes",
    "marisol" and "marisol reyes" all find the same person.
    """
    queryset = Professor.objects.all()

    if department:
        queryset = queryset.filter(department=department)

    for term in q.split():
        queryset = queryset.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term))

    spec = PROFESSOR_SORTS.get(sort) or PROFESSOR_SORTS["name"]
    return queryset.order_by(*spec.order_by)


# --------------------------------------------------------------------------
# Detail pages
# --------------------------------------------------------------------------
def get_course_by_code(code: str) -> Course | None:
    """Look up a course from its URL form ("CSC-240" -> "CSC 240")."""
    return Course.objects.filter(code__iexact=code.replace("-", " ").strip()).first()


def professors_for_course(course: Course) -> list[Professor]:
    """Resolve Course.professor_ids in one query. No $lookup, no prefetch_related."""
    if not course.professor_ids:
        return []
    found = Professor.objects.filter(pk__in=course.professor_ids)
    return sorted(found, key=lambda p: (p.last_name, p.first_name))


def courses_for_professor(professor: Professor) -> list[Course]:
    """Resolve Professor.course_ids in one query."""
    if not professor.course_ids:
        return []
    return sorted(Course.objects.filter(pk__in=professor.course_ids), key=lambda c: c.code)


def link_course_and_professor(course: Course, professor: Professor) -> None:
    """
    Write both sides of the relationship.

    Nothing enforces this pairing at the database level, so it lives in one
    function rather than being open-coded wherever a link is made.
    """
    if professor.pk not in course.professor_ids:
        course.professor_ids = [*course.professor_ids, professor.pk]
        course.save(update_fields=["professor_ids"])
    if course.pk not in professor.course_ids:
        professor.course_ids = [*professor.course_ids, course.pk]
        professor.save(update_fields=["course_ids"])


# --------------------------------------------------------------------------
# Landing page
# --------------------------------------------------------------------------
def landing_snapshot() -> dict:
    """
    Real records for the landing page, so it shows the product rather than
    stock imagery or placeholder copy.

    The featured professor's rating is RateMyProfessors data. Anything that
    renders it must say so (see CLAUDE.md), which the template does.
    """
    featured_course = Course.objects.filter(code="CSC 229").first() or Course.objects.first()
    featured_professor = (
        Professor.objects.exclude(rating_summary__count=0)
        .order_by(F("rating_summary__rank_score").desc(nulls_last=True))
        .first()
    )
    department_count = len(course_departments())
    return {
        "course_count": Course.objects.count(),
        "professor_count": Professor.objects.count(),
        "department_count": department_count,
        "featured_course": featured_course,
        "featured_professor": featured_professor,
        # A slow-drifting backdrop of genuine course codes for the hero.
        "code_wall": list(
            Course.objects.order_by("code").values_list("code", flat=True)[
                :: max(1, Course.objects.count() // 90)
            ][:90]
        ),
    }
