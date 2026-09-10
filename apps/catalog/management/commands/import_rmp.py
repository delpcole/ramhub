"""
Import RateMyProfessors aggregates onto matching directory professors.

Source: apps/catalog/seed_data/farmingdale_rmp.json — 1,634 records pulled from
RMP's public GraphQL endpoint for school 14046. See the .README.md beside it for
method, caveats and terms of use, and fetch_rmp.py to refresh it.

WHAT THIS COMMAND DOES THAT NOTHING ELSE DOES
---------------------------------------------
It writes ratings RamHub did not receive from its own students. That is a
deliberate decision, taken knowingly, and it is why every number it writes is
tagged ``rating_summary.source = "rmp"`` and labelled as RateMyProfessors data
everywhere it is displayed. Do not strip that attribution.

Mapping, and its limits:

* RMP's ``avgRating`` is a single "quality" score. It goes to ``avg_overall``.
* ``avg_clarity`` / ``avg_helpfulness`` / ``avg_fairness`` stay **null**. RMP has
  no equivalent, and splitting one number into three would invent detail.
* Difficulty and would-take-again have no home in rating_summary at all, so they
  live in the ``rmp_*`` fields, which stay the source of truth.

Ratings a student leaves on RamHub always win: a professor whose summary is
already ``source="ramhub"`` is skipped, never overwritten.

Matching is on normalised first+last name. Roughly 60% of directory staff match;
the rest keep no ratings and fall back to an RMP search link. Where RMP holds
several profiles for one name — students sometimes create a second rather than
find the first — the one with the most ratings wins.
"""

import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Professor, ProfessorRatingSummary

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "seed_data" / "farmingdale_rmp.json"
# The collection date recorded in farmingdale_rmp.README.md.
DEFAULT_RETRIEVED = "2026-09-10"

_TITLES = re.compile(r"\b(dr|prof|professor|mr|mrs|ms)\b\.?")


def normalize_name(first: str, last: str) -> tuple[str, str]:
    """Fold accents, drop titles and punctuation, lowercase — both sides alike."""

    def clean(value: str) -> str:
        value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
        value = _TITLES.sub(" ", value.lower())
        return " ".join(re.sub(r"[^a-z ]", " ", value).split())

    return clean(first), clean(last)


class Command(BaseCommand):
    help = "Attach RateMyProfessors ratings to matching professors."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--file", default=str(DATA_FILE), help="Path to the RMP .json export.")
        parser.add_argument(
            "--retrieved", default=DEFAULT_RETRIEVED, help="Collection date (YYYY-MM-DD)."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all RMP data and RMP-sourced ratings instead of importing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["clear"]:
            self._clear()
            return

        records = self._load(Path(options["file"]))
        try:
            retrieved = date.fromisoformat(options["retrieved"])
        except ValueError as exc:
            raise CommandError(f"--retrieved must be YYYY-MM-DD: {exc}") from exc

        self._import(records, retrieved)

    # -- steps -------------------------------------------------------------

    def _load(self, path: Path) -> dict[tuple[str, str], dict]:
        if not path.exists():
            raise CommandError(f"RMP export not found at {path}")
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            grouped[normalize_name(row.get("firstName", ""), row.get("lastName", ""))].append(row)

        # Students sometimes create a second profile instead of finding the
        # first. The one carrying the most ratings is the one people read.
        self.ambiguous = sum(1 for group in grouped.values() if len(group) > 1)
        return {
            key: max(group, key=lambda r: r.get("numRatings") or 0)
            for key, group in grouped.items()
        }

    def _import(self, records: dict[tuple[str, str], dict], retrieved: date) -> None:
        matched = rated = protected = 0

        for professor in Professor.objects.all():
            record = records.get(normalize_name(professor.first_name, professor.last_name))
            if record is None:
                continue
            matched += 1

            summary = professor.rating_summary
            if summary.source == ProfessorRatingSummary.SOURCE_RAMHUB and summary.count:
                # Real student ratings outrank an imported aggregate, always.
                protected += 1
                continue

            count = record.get("numRatings") or 0
            professor.rmp_legacy_id = record.get("legacyId")
            professor.rmp_num_ratings = count
            professor.rmp_avg_rating = self._score(record.get("avgRating"), count)
            professor.rmp_avg_difficulty = self._score(record.get("avgDifficulty"), count)
            professor.rmp_would_take_again_pct = self._percent(record.get("wouldTakeAgainPercent"))
            professor.rmp_retrieved = retrieved

            if count:
                professor.rating_summary = ProfessorRatingSummary(
                    # RMP publishes one quality score, so only avg_overall is
                    # populated. The three sub-axes have no RMP equivalent.
                    avg_overall=professor.rmp_avg_rating,
                    count=count,
                    source=ProfessorRatingSummary.SOURCE_RMP,
                    rank_score=ProfessorRatingSummary.compute_rank_score(
                        professor.rmp_avg_rating, count
                    ),
                )
                rated += 1
            professor.save()

        self._report(matched, rated, protected)

    @staticmethod
    def _score(value, count: int) -> float | None:
        """RMP sends 0 for an unrated professor; that is absence, not a zero score."""
        if not count or value in (None, 0):
            return None
        return round(float(value), 2)

    @staticmethod
    def _percent(value) -> float | None:
        """RMP sends -1 when it has no would-take-again data."""
        if value is None or value < 0:
            return None
        return round(float(value), 1)

    def _clear(self) -> None:
        cleared = 0
        for professor in Professor.objects.exclude(rmp_legacy_id__isnull=True):
            professor.rmp_legacy_id = None
            professor.rmp_avg_rating = None
            professor.rmp_avg_difficulty = None
            professor.rmp_would_take_again_pct = None
            professor.rmp_num_ratings = 0
            professor.rmp_retrieved = None
            if professor.rating_summary.is_from_rmp:
                professor.rating_summary = ProfessorRatingSummary()
            professor.save()
            cleared += 1
        self.stdout.write(self.style.WARNING(f"Cleared RMP data from {cleared} professors."))

    # -- output ------------------------------------------------------------

    def _report(self, matched: int, rated: int, protected: int) -> None:
        total = Professor.objects.count()
        self.stdout.write("")
        self.stdout.write(f"  Matched     {matched:>5} of {total} professors by name")
        self.stdout.write(f"  Rated       {rated:>5} now carry RateMyProfessors scores")
        self.stdout.write(
            f"  Unmatched   {total - matched:>5} keep no ratings and an RMP search link"
        )
        if self.ambiguous:
            self.stdout.write(
                f"  Ambiguous   {self.ambiguous:>5} names had several RMP profiles; "
                "the most-rated one was used"
            )
        if protected:
            self.stdout.write(f"  Protected   {protected:>5} kept their RamHub student ratings")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "These ratings came from RateMyProfessors, not from RamHub students. "
                'They are tagged source="rmp" and must stay labelled as such wherever shown.'
            )
        )
