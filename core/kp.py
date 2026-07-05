"""KP (Krishnamurti Paddhati) lordship chains and significators.

Each nakshatra (13deg20') is subdivided using Vimsottari proportions to yield a
sub-lord, and each sub is subdivided again to yield a sub-sub-lord. The chain for
any longitude is: sign-lord -> star (nakshatra) lord -> sub-lord -> sub-sub-lord.
"""
from __future__ import annotations

from dataclasses import dataclass

from core import constants as C


@dataclass(frozen=True)
class KPLords:
    sign_lord: str
    star_lord: str
    sub_lord: str
    sub_sub_lord: str


def _vimsottari_from(start_lord: str):
    """Yield (lord, years) in Vimsottari order starting at ``start_lord``."""
    order = C.VIMSOTTARI_ORDER
    idx = order.index(start_lord)
    for i in range(len(order)):
        lord = order[(idx + i) % len(order)]
        yield lord, C.VIMSOTTARI_YEARS[lord]


def subdivide(offset: float, total: float, start_lord: str) -> tuple[str, float, float]:
    """Locate ``offset`` within a span of length ``total`` divided by Vimsottari
    proportions starting at ``start_lord``.

    Returns (lord, span_start, span_length) of the division containing offset.
    """
    cursor = 0.0
    lord = start_lord
    length = 0.0
    start = 0.0
    for lord, years in _vimsottari_from(start_lord):
        length = years / C.VIMSOTTARI_TOTAL_YEARS * total
        start = cursor
        cursor += length
        if offset < cursor:
            return lord, start, length
    # Floating point may leave offset a hair past the end; return the last span.
    return lord, start, length


def planet_house(longitude: float, houses) -> int:
    """Cuspal house (1..12) a longitude falls in, using KP cusp boundaries.

    House N spans forward from cusp N up to (not including) cusp N+1.
    """
    longitude = longitude % 360.0
    cusps = houses.cusps
    for n in range(12):
        start = cusps[n].longitude
        end = cusps[(n + 1) % 12].longitude
        arc = (end - start) % 360.0
        offset = (longitude - start) % 360.0
        # arc == 0 would mean a degenerate house; treat offset 0 as inside.
        if offset < arc or (arc == 0.0 and offset == 0.0):
            return cusps[n].house
    return 12  # numerical safety net


def houses_owned(planet: str, houses) -> list[int]:
    """Houses whose cusp sign-lord is ``planet`` (KP house ownership by cusp)."""
    return [c.house for c in houses.cusps if c.sign_lord == planet]


def _star_lord_of_planet(graha) -> str:
    return graha.nakshatra_lord


def planet_significators(grahas: dict, houses) -> dict:
    """KP 4-fold significators per planet.

    For planet P (strongest -> weakest):
      1. houses occupied by P's star-lord
      2. houses owned by P's star-lord
      3. houses occupied by P
      4. houses owned by P
    """
    occupied_house = {name: planet_house(g.longitude, houses) for name, g in grahas.items()}

    result: dict[str, dict] = {}
    for name, graha in grahas.items():
        star_lord = _star_lord_of_planet(graha)
        star_lord_graha = grahas.get(star_lord)

        occ_by_star = [occupied_house[star_lord]] if star_lord_graha else []
        owned_by_star = houses_owned(star_lord, houses)
        occ = [occupied_house[name]]
        owned = houses_owned(name, houses)

        houses_union = sorted(set(occ_by_star) | set(owned_by_star) | set(occ) | set(owned))
        result[name] = {
            "occupied_by_star_lord": occ_by_star,
            "owned_by_star_lord": owned_by_star,
            "occupied": occ,
            "owned": owned,
            "houses": houses_union,
        }
    return result


def house_significators(grahas: dict, houses) -> dict:
    """Inverse of planet_significators: house (1..12) -> planets signifying it."""
    psig = planet_significators(grahas, houses)
    result: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for planet, data in psig.items():
        for house_num in data["houses"]:
            result[house_num].append(planet)
    return result


def kp_lords(longitude: float) -> KPLords:
    longitude = longitude % 360.0

    sign_index = int(longitude // 30)
    sign_lord = C.SIGN_LORDS[sign_index]

    nak_index = int(longitude // C.NAKSHATRA_ARC)
    star_lord = C.NAKSHATRA_LORDS[nak_index]

    offset_in_nak = longitude - nak_index * C.NAKSHATRA_ARC
    sub_lord, sub_start, sub_len = subdivide(offset_in_nak, C.NAKSHATRA_ARC, star_lord)

    offset_in_sub = offset_in_nak - sub_start
    sub_sub_lord, _, _ = subdivide(offset_in_sub, sub_len, sub_lord)

    return KPLords(
        sign_lord=sign_lord,
        star_lord=star_lord,
        sub_lord=sub_lord,
        sub_sub_lord=sub_sub_lord,
    )
