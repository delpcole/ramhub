"""
Data for the landing page at "/".

Split out of services.py to keep both modules under the ~300-line ceiling in
CLAUDE.md. Everything here is read-only and derived from real records: the
landing page must never show a number or a claim the database cannot back up.
"""

from django.db.models import F

from .models import Course, Professor
from .services import course_departments


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
    course_count = Course.objects.count()
    return {
        "course_count": course_count,
        "rambo_lines": rambo_lines(course_count, department_count, featured_course),
        "features": landing_features(course_count, department_count),
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


def rambo_lines(
    course_count: int, department_count: int, featured_course: Course | None
) -> list[str]:
    """
    What Rambo says when you nudge him. Every line is true of the live
    database, so the mascot never makes a claim the site cannot back up.
    Rambo's question-answering assistant is not built yet, and his lines say so
    rather than implying it works.
    """
    lines = [
        "Hi, I'm Rambo.",
        f"There are {course_count:,} courses in here. Go on, look one up.",
        f"{department_count} departments. I have read every one of them.",
    ]
    if featured_course:
        lines.append(f"Heard about {featured_course.code}? Worth checking before you register.")
    lines += [
        "Advice from students who already took the class. That is the whole idea.",
        "I will be answering your questions soon. For now, I mostly nod.",
    ]
    return lines


def landing_features(course_count: int, department_count: int) -> list[dict[str, str]]:
    """
    The feature strip on the landing page: one card per section of the site.

    Each card links to a page that genuinely exists. `detail` is honest about
    the state of each one — the catalog and directory hold real college data,
    while the campus tabs render an empty state until their data is imported.
    Saying "coming soon" about a page that is already live, or implying data
    that is not there, both count as lying to a prospective user.
    """
    professor_count = Professor.objects.count()
    rated = Professor.objects.exclude(rating_summary__count=0).count()
    return [
        {
            "label": "Courses",
            "url_name": "catalog:courses",
            "icon": "book",
            "detail": f"{course_count:,} courses across {department_count} departments",
            "blurb": "The published catalog, searchable by code or title, with prerequisites.",
            "status": "live",
        },
        {
            "label": "Professors",
            "url_name": "catalog:professors",
            "icon": "users",
            "detail": f"{professor_count:,} instructors, {rated:,} with ratings",
            "blurb": "Every instructor in the campus directory, with office hours and contact details.",
            "status": "live",
        },
        {
            "label": "Feed",
            "url_name": "community:feed",
            "icon": "chat",
            "detail": "Opens with accounts",
            "blurb": "Campus-wide discussion for anything that is not tied to one course.",
            "status": "building",
        },
        {
            "label": "Clubs",
            "url_name": "campus:clubs",
            "icon": "flag",
            "detail": "Awaiting the club directory",
            "blurb": "Every registered organisation: what it does, when it meets, how to join.",
            "status": "building",
        },
        {
            "label": "Jobs",
            "url_name": "campus:jobs",
            "icon": "briefcase",
            "detail": "Awaiting listings",
            "blurb": "On-campus work, work-study and internships, plus leads posted by students.",
            "status": "building",
        },
        {
            "label": "Parking",
            "url_name": "campus:parking",
            "icon": "car",
            "detail": "Awaiting lot data",
            "blurb": "The lots, the permits, the rules — and which ones fill up before nine.",
            "status": "building",
        },
        {
            "label": "Facilities",
            "url_name": "campus:facilities",
            "icon": "building",
            "detail": "Awaiting building hours",
            "blurb": "Buildings, labs, study spaces and dining, with the hours that actually apply.",
            "status": "building",
        },
    ]
