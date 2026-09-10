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

from urllib.parse import quote_plus

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
    # Stored, not computed: the professors directory sorts on it, and MongoDB
    # cannot order by a Python property. Whatever writes ratings must call
    # compute_overall() and store the result alongside the three axes.
    #
    # Courses deliberately have no equivalent. Difficulty, workload, and
    # usefulness are not a single quality axis — a hard course is not a bad one
    # — so averaging them would produce a number that means nothing. The
    # courses directory sorts on the specific axis the reader asked for.
    avg_overall = models.FloatField(null=True, blank=True)
    count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.count} ratings"

    @property
    def has_ratings(self) -> bool:
        return self.count > 0

    @staticmethod
    def compute_overall(
        clarity: float | None, helpfulness: float | None, fairness: float | None
    ) -> float | None:
        """Mean of whichever axes are known. None when none are."""
        known = [v for v in (clarity, helpfulness, fairness) if v is not None]
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


# RateMyProfessors' internal id for Farmingdale State College, used to scope the
# lookup link on a professor page to this campus.
RMP_SCHOOL_ID = "14046"
RMP_SEARCH_URL = "https://www.ratemyprofessors.com/search/professors/{school}?q={query}"


class Professor(models.Model):
    # Stable, human-readable key straight from the college directory
    # ("melixa-abad-izquierdo"). It is the URL and the import's natural key.
    slug = models.SlugField(max_length=120, unique=True)

    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    department = models.CharField(max_length=120)
    title = models.CharField(max_length=160, blank=True, help_text="e.g. Associate Professor.")
    photo = models.URLField(blank=True)
    bio = models.TextField(blank=True)

    # --- Facts imported from the official directory -----------------------
    # These are the college's data, not ours. import_directory overwrites them
    # on every run; nothing in the app should edit them.
    faculty_id = models.CharField(max_length=16, blank=True)
    profile_url = models.URLField(blank=True, help_text="Official faculty page.")
    department_url = models.URLField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    office = models.CharField(max_length=160, blank=True)
    directory_retrieved = models.DateField(
        null=True, blank=True, help_text="When the directory row was last pulled."
    )

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

    @property
    def rmp_search_url(self) -> str:
        """
        A RateMyProfessors lookup for this person, scoped to Farmingdale.

        Deliberately a search rather than a deep link: the college directory
        carries no RMP ids, and RMP holds duplicate and differently-spelled
        entries for the same person. A search lets the reader pick the right
        one instead of us guessing an id and sending them to the wrong page.
        """
        return RMP_SEARCH_URL.format(school=RMP_SCHOOL_ID, query=quote_plus(self.full_name))
