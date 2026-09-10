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

    # Where these numbers came from. Without it the UI cannot tell a rating a
    # student left on RamHub from an aggregate imported off RateMyProfessors,
    # and it must, because those are not the same claim.
    SOURCE_RAMHUB = "ramhub"
    SOURCE_RMP = "rmp"
    SOURCE_CHOICES = [
        (SOURCE_RAMHUB, "Students on RamHub"),
        (SOURCE_RMP, "RateMyProfessors"),
    ]
    source = models.CharField(max_length=16, blank=True, choices=SOURCE_CHOICES)

    # What "Highest rated" actually sorts on. A raw average ranks a 5.0 from a
    # single rating above a 4.9 from 226, which is not what a reader means by
    # "highest rated". This is a Bayesian average — it pulls thinly-rated
    # professors toward the overall mean until they have enough ratings to earn
    # their position — stored because MongoDB cannot order by a computed value.
    # The displayed number stays the true average; only the ordering uses this.
    rank_score = models.FloatField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.count} ratings"

    @property
    def has_ratings(self) -> bool:
        return self.count > 0

    @property
    def is_from_rmp(self) -> bool:
        return self.source == self.SOURCE_RMP

    # Ratings needed before a professor's own average dominates the prior, and
    # the mean rating to pull toward. 3.71 is the mean across rated Farmingdale
    # professors on RMP; see farmingdale_rmp.README.md.
    RANK_PRIOR_COUNT = 10
    RANK_PRIOR_MEAN = 3.71

    @classmethod
    def compute_rank_score(cls, average: float | None, count: int) -> float | None:
        """Bayesian average: (v*R + m*C) / (v + m)."""
        if average is None or not count:
            return None
        v, m, c = count, cls.RANK_PRIOR_COUNT, cls.RANK_PRIOR_MEAN
        return round((v * average + m * c) / (v + m), 4)

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
    # Nullable on purpose: 23 real catalog entries publish no credit value, only
    # lecture/lab hours like "(1,0)" which are not credits. A default of 3 would
    # be inventing a fact about a real course.
    credits = models.PositiveSmallIntegerField(null=True, blank=True)
    department = models.CharField(max_length=120)
    subject = models.CharField(max_length=8, blank=True, help_text="Code prefix, e.g. CSC.")
    prereq_text = models.TextField(blank=True, help_text="Free text, as the catalog prints it.")
    coreq_text = models.TextField(blank=True, help_text="Free text, as the catalog prints it.")
    catalog_year = models.CharField(max_length=16, blank=True, help_text="e.g. 2025-2026.")

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
RMP_PROFILE_URL = "https://www.ratemyprofessors.com/professor/{legacy_id}"


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

    # --- RateMyProfessors ------------------------------------------------
    # Third-party data about a real person, kept in its own fields so its
    # provenance is never lost. rating_summary mirrors the headline number so
    # the existing directory UI works; these stay the source of truth.
    rmp_legacy_id = models.PositiveIntegerField(
        null=True, blank=True, help_text="RMP's stable professor id; enables a direct link."
    )
    rmp_avg_rating = models.FloatField(null=True, blank=True, help_text="RMP quality, 1-5.")
    rmp_avg_difficulty = models.FloatField(null=True, blank=True, help_text="RMP difficulty, 1-5.")
    rmp_would_take_again_pct = models.FloatField(null=True, blank=True)
    rmp_num_ratings = models.PositiveIntegerField(default=0)
    rmp_retrieved = models.DateField(null=True, blank=True)

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
    def rmp_url(self) -> str:
        """
        Where to send someone who wants this professor on RateMyProfessors.

        A direct profile link once the RMP import has matched an id, and a
        school-scoped search otherwise. The fallback matters: only about 60% of
        directory staff match an RMP record, and RMP holds duplicate entries for
        the same person, so a search is the honest answer when we are not sure.
        """
        if self.rmp_legacy_id:
            return RMP_PROFILE_URL.format(legacy_id=self.rmp_legacy_id)
        return RMP_SEARCH_URL.format(school=RMP_SCHOOL_ID, query=quote_plus(self.full_name))

    @property
    def has_rmp_profile(self) -> bool:
        return self.rmp_legacy_id is not None
