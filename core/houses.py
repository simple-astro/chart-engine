"""Lagna (ascendant) and house cusps.

House system is bound to the ayanamsha mode (FR-3.3a): Placidus in KP mode,
whole-sign in classical/Lahiri mode.
"""
from __future__ import annotations

from dataclasses import dataclass

import swisseph as swe

from core import constants as C
from core.ephemeris import set_sidereal_mode


@dataclass(frozen=True)
class Cusp:
    house: int                # 1..12
    longitude: float          # sidereal ecliptic longitude, 0..360
    sign_index: int           # 0..11
    sign: str
    sign_lord: str
    degrees_in_sign: float


@dataclass(frozen=True)
class Houses:
    ascendant: float
    midheaven: float
    house_system: str         # 'placidus' | 'whole_sign'
    cusps: list[Cusp]         # 12 entries, house 1..12


def _make_cusp(house: int, longitude: float) -> Cusp:
    longitude = longitude % 360.0
    sign_index = int(longitude // 30)
    return Cusp(
        house=house,
        longitude=longitude,
        sign_index=sign_index,
        sign=C.SIGNS[sign_index],
        sign_lord=C.SIGN_LORDS[sign_index],
        degrees_in_sign=longitude % 30.0,
    )


def compute_houses(jd: float, lat: float, lon: float, ayanamsha: str) -> Houses:
    set_sidereal_mode(ayanamsha)
    system = C.HOUSE_SYSTEM_FOR_AYANAMSHA[ayanamsha]

    # Placidus cusps come from Swiss Ephemeris in the sidereal frame.
    cusps_raw, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    ascendant = ascmc[0] % 360.0
    midheaven = ascmc[1] % 360.0

    if system == "placidus":
        # pyswisseph returns a 12-element, 0-indexed cusp tuple (index 0 = house 1).
        cusps = [_make_cusp(i + 1, cusps_raw[i]) for i in range(12)]
    else:  # whole_sign
        sign_start = (int(ascendant // 30)) * 30.0
        cusps = [_make_cusp(i + 1, sign_start + 30.0 * i) for i in range(12)]

    return Houses(
        ascendant=ascendant,
        midheaven=midheaven,
        house_system=system,
        cusps=cusps,
    )
