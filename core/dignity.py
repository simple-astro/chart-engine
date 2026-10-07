"""Planetary dignity by sign (same rules as the website's insights.js)."""
from __future__ import annotations

from core.constants import SIGN_LORDS

EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6, "Rahu": 1, "Ketu": 7}
FRIENDS = {"Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"}, "Mars": {"Sun", "Moon", "Jupiter"},
           "Mercury": {"Sun", "Venus"}, "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
           "Saturn": {"Mercury", "Venus"}, "Rahu": {"Mercury", "Venus", "Saturn"}, "Ketu": {"Mars", "Jupiter"}}
ENEMIES = {"Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"}, "Mercury": {"Moon"},
           "Jupiter": {"Mercury", "Venus"}, "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"},
           "Rahu": {"Sun", "Moon", "Mars"}, "Ketu": {"Moon", "Venus"}}


def dignity(planet: str, sign: int) -> str:
    """exalted | debilitated | own | friendly | enemy | neutral"""
    if EXALT[planet] == sign:
        return "exalted"
    if (EXALT[planet] + 6) % 12 == sign:
        return "debilitated"
    lord = SIGN_LORDS[sign]
    if lord == planet:
        return "own"
    if lord in FRIENDS[planet]:
        return "friendly"
    return "enemy" if lord in ENEMIES[planet] else "neutral"
