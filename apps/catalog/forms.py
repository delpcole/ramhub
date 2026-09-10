"""
Query-string validation for the two directory pages.

Nothing reads request.GET directly. These forms are deliberately lenient: a
directory URL is something people bookmark and share, so an unknown sort key or
a junk page number falls back to the default instead of returning a 400. What
they guarantee is that the view never passes unvalidated input to a query.
"""

from typing import Any, NamedTuple

from django import forms

from .services import COURSE_SORTS, PROFESSOR_SORTS

MAX_QUERY_LENGTH = 100


class DirectoryQuery(NamedTuple):
    """Validated, defaulted directory parameters."""

    q: str
    department: str
    sort: str
    page: int
    append: bool


class BaseDirectoryForm(forms.Form):
    """Shared shape. Subclasses supply the valid sort keys."""

    sort_choices: dict[str, str] = {}
    default_sort: str = ""

    q = forms.CharField(required=False, max_length=MAX_QUERY_LENGTH, strip=True)
    department = forms.CharField(required=False, max_length=64, strip=True)
    page = forms.IntegerField(required=False, min_value=1, max_value=10_000)
    append = forms.BooleanField(required=False)

    def __init__(self, *args: Any, departments: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.allowed_departments = set(departments or [])
        self.fields["sort"] = forms.ChoiceField(
            required=False,
            choices=[(key, label) for key, label in self.sort_choices.items()],
        )

    def clean_department(self) -> str:
        """Silently drop a department that no longer exists."""
        value = self.cleaned_data.get("department", "")
        return value if value in self.allowed_departments else ""

    def to_query(self) -> DirectoryQuery:
        """
        Return usable parameters whether or not the form validated.

        Invalid fields fall back to their defaults rather than failing the page.
        """
        self.is_valid()
        data = self.cleaned_data
        sort = data.get("sort") or self.default_sort
        if sort not in self.sort_choices:
            sort = self.default_sort
        return DirectoryQuery(
            q=(data.get("q") or "").strip(),
            department=data.get("department") or "",
            sort=sort,
            page=data.get("page") or 1,
            append=bool(data.get("append")),
        )


class CourseDirectoryForm(BaseDirectoryForm):
    sort_choices = {key: spec.label for key, spec in COURSE_SORTS.items()}
    default_sort = "code"


class ProfessorDirectoryForm(BaseDirectoryForm):
    sort_choices = {key: spec.label for key, spec in PROFESSOR_SORTS.items()}
    default_sort = "name"
