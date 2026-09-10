"""
The admin changelists have to render for both rated and unrated records.

These exist because a Phase 1 refactor replaced ProfessorRatingSummary.overall
with a stored avg_overall field and left admin.py calling the old property. The
admin had no coverage, so nothing failed until someone opened the page.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_(client):
    user = User.objects.create_superuser("staff", "staff@farmingdale.edu", "pw-not-a-real-secret")
    client.force_login(user)
    return client


@pytest.fixture
def records(make_course, make_professor):
    make_course(
        code="CSC 240",
        title="Data Structures",
        difficulty=4.6,
        workload=4.5,
        usefulness=4.3,
        count=40,
    )
    make_course(code="CSC 440", title="Computer Networks")
    make_professor(
        first_name="Marisol",
        last_name="Reyes",
        clarity=4.5,
        helpfulness=4.2,
        fairness=4.0,
        count=63,
    )
    make_professor(first_name="Colleen", last_name="Doyle")


@pytest.mark.parametrize("model", ["course", "professor"])
def test_changelist_renders(admin_client_, records, model):
    response = admin_client_.get(reverse(f"admin:catalog_{model}_changelist"))

    assert response.status_code == 200
    assert b"no ratings" in response.content, "the unrated row should say so"


@pytest.mark.parametrize("model", ["course", "professor"])
def test_changelist_search_and_filter_render(admin_client_, records, model):
    base = reverse(f"admin:catalog_{model}_changelist")

    assert admin_client_.get(base, {"q": "Reyes"}).status_code == 200
    assert admin_client_.get(base, {"department__exact": "Testing"}).status_code == 200


def test_professor_changelist_shows_the_stored_overall(admin_client_, records):
    """Guards the exact regression above: admin must not call a removed property."""
    response = admin_client_.get(reverse("admin:catalog_professor_changelist"))

    assert b"overall 4.23" in response.content


@pytest.mark.parametrize("model", ["course", "professor"])
def test_change_form_renders(admin_client_, records, model):
    from apps.catalog.models import Course, Professor

    obj = (Course if model == "course" else Professor).objects.first()
    response = admin_client_.get(reverse(f"admin:catalog_{model}_change", args=[obj.pk]))

    assert response.status_code == 200
