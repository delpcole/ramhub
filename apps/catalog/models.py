"""
Course and Professor — the spine of the knowledge base.

Everything else hangs off these two: ratings attach to them, advice threads
attach to them, the filing cabinet saves them, and the assistant indexes them.

Two MongoDB decisions are baked in here and are hard to change later, so they
are spelled out:

1. The Course <-> Professor relationship is an ``ArrayField`` of ObjectIds on
   *both* sides, not a ForeignKey or ManyToManyField. Resolving it is a single
   ``filter(pk__in=...)`` rather than a ``$lookup``. Both sides must be written
   together — see ``services.link_course_and_professor``.
2. ``rating_summary`` is an embedded document, always present. "Nobody has rated
   this yet" is ``count == 0`` with null averages — never a missing or null
   ``rating_summary``. Migrations do not rewrite existing documents and embedded
   indexes cannot be altered after the collection exists, so this shape needs to
   be right the first time.
"""

from django.db import models
from django_mongodb_backend.fields import ArrayField, EmbeddedModelField, ObjectIdField
from django_mongodb_backend.models import EmbeddedModel


class CourseRatingSummary(EmbeddedModel):
    """Denormalized course ratings. Written by whatever creates ratings — never
    recomputed with a live aggregation on a list page."""

    avg_difficulty = models.FloatField(null=True, blank=True)
    avg_workload = models.FloatField(null=True, blank=True)
    avg_usefulness = models.FloatField(null=True, blank=True)
    count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.count} ratings"

    @property
    def has_ratings(self) -> bool:
        return self.count > 0


class ProfessorRatingSummary(EmbeddedModel):
    """Denormalized professor ratings. Same rules as CourseRatingSummary."""

    avg_clarity = models.FloatField(null=True, blank=True)
    avg_helpfulness = models.FloatField(null=True, blank=True)
    avg_fairness = models.FloatField(null=True, blank=True)
    count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.count} ratings"

    @property
    def has_ratings(self) -> bool:
        return self.count > 0

    @property
    def overall(self) -> float | None:
        """The single number shown on directory rows. None until someone rates."""
        if not self.has_ratings:
            return None
        parts = [self.avg_clarity, self.avg_helpfulness, self.avg_fairness]
        known = [p for p in parts if p is not None]
        return round(sum(known) / len(known), 2) if known else None


class Course(models.Model):
    code = models.CharField(max_length=16, help_text="Catalog code, e.g. CSC 240.")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.PositiveSmallIntegerField(default=3)
    department = models.CharField(max_length=64)
    prereq_text = models.TextField(blank=True, help_text="Free text, as the catalog prints it.")

    # M2M replacement. Kept in sync with Professor.course_ids.
    professor_ids = ArrayField(ObjectIdField(), default=list, blank=True)

    rating_summary = EmbeddedModelField(CourseRatingSummary, default=CourseRatingSummary)

    class Meta:
        ordering = ["code"]
        constraints = [
            # Course code is the natural key: it is how seed_demo stays
            # idempotent and how /courses/<code>/ resolves.
            models.UniqueConstraint(fields=["code"], name="catalog_course_code_unique"),
        ]
        indexes = [
            # The only filter the directory offers.
            models.Index(fields=["department"], name="catalog_course_dept_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"

    @property
    def slug(self) -> str:
        """URL form of the code: "CSC 240" -> "CSC-240"."""
        return self.code.replace(" ", "-")


class Professor(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    department = models.CharField(max_length=64)
    title = models.CharField(max_length=64, blank=True, help_text="e.g. Associate Professor.")
    photo = models.URLField(blank=True)
    bio = models.TextField(blank=True)

    # M2M replacement. Kept in sync with Course.professor_ids.
    course_ids = ArrayField(ObjectIdField(), default=list, blank=True)

    rating_summary = EmbeddedModelField(ProfessorRatingSummary, default=ProfessorRatingSummary)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            # Directory filter.
            models.Index(fields=["department"], name="catalog_prof_dept_idx"),
            # Default sort order for the directory, and the name search entry point.
            models.Index(fields=["last_name", "first_name"], name="catalog_prof_name_idx"),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
