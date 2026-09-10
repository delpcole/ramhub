"""Presentation helpers for the catalog templates."""

from django import template

register = template.Library()

RATING_SCALE = 5.0


@register.filter
def rating_pct(value: float | None) -> str:
    """
    A 1-5 rating as a CSS width percentage for .rating-bar-fill.

    Returns "0%" for an unrated record; templates should show the "no ratings"
    state rather than an empty bar in that case.
    """
    try:
        fraction = max(0.0, min(float(value) / RATING_SCALE, 1.0))
    except (TypeError, ValueError):
        return "0%"
    return f"{fraction * 100:.1f}%"
