"""Factory helpers for the catalog tests."""

import pytest
from django.utils.text import slugify

from apps.catalog.models import (
    Course,
    CourseRatingSummary,
    Professor,
    ProfessorRatingSummary,
)


@pytest.fixture
def make_course():
    def _make(code="TST 101", title="Test Course", department="Testing", credits=3, **kwargs):
        summary = kwargs.pop("rating_summary", None)
        if summary is None:
            summary = CourseRatingSummary(
                avg_difficulty=kwargs.pop("difficulty", None),
                avg_workload=kwargs.pop("workload", None),
                avg_usefulness=kwargs.pop("usefulness", None),
                count=kwargs.pop("count", 0),
            )
        return Course.objects.create(
            code=code,
            title=title,
            department=department,
            credits=credits,
            rating_summary=summary,
            **kwargs,
        )

    return _make


@pytest.fixture
def make_professor():
    def _make(first_name="Ada", last_name="Lovelace", department="Testing", **kwargs):
        kwargs.setdefault("slug", slugify(f"{first_name} {last_name}"))
        summary = kwargs.pop("rating_summary", None)
        if summary is None:
            clarity = kwargs.pop("clarity", None)
            helpfulness = kwargs.pop("helpfulness", None)
            fairness = kwargs.pop("fairness", None)
            summary = ProfessorRatingSummary(
                avg_clarity=clarity,
                avg_helpfulness=helpfulness,
                avg_fairness=fairness,
                avg_overall=ProfessorRatingSummary.compute_overall(clarity, helpfulness, fairness),
                count=kwargs.pop("count", 0),
            )
        return Professor.objects.create(
            first_name=first_name,
            last_name=last_name,
            department=department,
            rating_summary=summary,
            **kwargs,
        )

    return _make
