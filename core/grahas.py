"""Graha (planet) positions with rashi, nakshatra, pada, retrograde, combustion."""
from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from core import constants as C
from core.ephemeris import sidereal_longitude


@dataclass(frozen=True)
class Graha:
    name: str
    longitude: float          # sidereal ecliptic longitude, 0..360
    speed: float              # longitude speed, deg/day
    sign_index: int           # 0..11 (Aries..Pisces)
    sign: str
    sign_lord: str
    degrees_in_sign: float    # 0..30
    nakshatra_index: int      # 0..26
    nakshatra: str
    nakshatra_lord: str
    pada: int                 # 1..4
    retrograde: bool
    combust: bool


def _node_planet_id(node_type: str) -> int:
    if node_type == "mean":
        return swe.MEAN_NODE
    if node_type == "true":
        return swe.TRUE_NODE
    raise ValueError(f"node_type must be 'mean' or 'true', got {node_type!r}")


def _norm360(x: float) -> float:
    return x % 360.0


def _nakshatra_of(longitude: float) -> tuple[int, str, str, int]:
    idx = int(longitude // C.NAKSHATRA_ARC)
    pada = int((longitude % C.NAKSHATRA_ARC) // C.PADA_ARC) + 1
    return idx, C.NAKSHATRAS[idx], C.NAKSHATRA_LORDS[idx], pada


def _is_combust(name: str, longitude: float, sun_longitude: float) -> bool:
    orb = C.COMBUSTION_ORB.get(name)
    if orb is None:
        return False
    sep = abs((longitude - sun_longitude + 180.0) % 360.0 - 180.0)
    return sep <= orb


def compute_grahas(jd: float, ayanamsha: str, node_type: str = "mean") -> dict[str, Graha]:
    """Compute all nine grahas at Julian day ``jd`` for the given ayanamsha."""
    # Sun first — needed for combustion of the others.
    sun_lon, sun_speed = sidereal_longitude(jd, swe.SUN, ayanamsha)

    raw: dict[str, tuple[float, float, bool]] = {}
    for name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        lon, speed = sidereal_longitude(jd, C.SWE_PLANET[name], ayanamsha)
        raw[name] = (_norm360(lon), speed, speed < 0)

    # Nodes: Rahu from the chosen node model; Ketu exactly opposite. Both are
    # conventionally treated as retrograde.
    rahu_lon, rahu_speed = sidereal_longitude(jd, _node_planet_id(node_type), ayanamsha)
    rahu_lon = _norm360(rahu_lon)
    raw["Rahu"] = (rahu_lon, rahu_speed, True)
    raw["Ketu"] = (_norm360(rahu_lon + 180.0), rahu_speed, True)

    result: dict[str, Graha] = {}
    for name, (lon, speed, retro) in raw.items():
        sign_index = int(lon // 30)
        nak_idx, nak, nak_lord, pada = _nakshatra_of(lon)
        result[name] = Graha(
            name=name,
            longitude=lon,
            speed=speed,
            sign_index=sign_index,
            sign=C.SIGNS[sign_index],
            sign_lord=C.SIGN_LORDS[sign_index],
            degrees_in_sign=lon % 30.0,
            nakshatra_index=nak_idx,
            nakshatra=nak,
            nakshatra_lord=nak_lord,
            pada=pada,
            retrograde=retro,
            combust=_is_combust(name, lon, sun_lon),
        )
    return result
