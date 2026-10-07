"""Parivartana (lord exchange): two planets each sitting in a sign ruled by the other.
Classified by the houses involved, counted whole-sign from the lagna:
Dainya if either house is 6/8/12, else Khala if either is the 3rd, else Maha.
"""
from __future__ import annotations

from core.constants import SIGN_LORDS

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
DUSTHANA = {6, 8, 12}


def house_of(sign: int, lagna_sign: int) -> int:
    return (sign - lagna_sign) % 12 + 1


def exchanges(signs: dict[str, int], lagna_sign: int) -> list[dict]:
    out = []
    for i, a in enumerate(PLANETS):
        for b in PLANETS[i + 1:]:
            if SIGN_LORDS[signs[a]] == b and SIGN_LORDS[signs[b]] == a:
                ha, hb = house_of(signs[a], lagna_sign), house_of(signs[b], lagna_sign)
                kind = ("Dainya" if {ha, hb} & DUSTHANA else "Khala" if 3 in (ha, hb) else "Maha")
                # a sits in b's sign, so a's house is one b rules and vice versa
                out.append({"planets": [a, b], "houses": [ha, hb], "type": kind,
                            "signs": [signs[a], signs[b]]})
    return out


def lord_placements(signs: dict[str, int], lagna_sign: int) -> list[dict]:
    """For each house: its sign, lord, and the house the lord sits in."""
    rows = []
    for h in range(1, 13):
        sign = (lagna_sign + h - 1) % 12
        lord = SIGN_LORDS[sign]
        rows.append({"house": h, "sign_index": sign, "lord": lord,
                     "lord_in": house_of(signs[lord], lagna_sign)})
    return rows
