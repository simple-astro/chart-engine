"""Low-level Swiss Ephemeris access: time, ayanamsha, sidereal positions.

Uses the built-in Moshier model (FLG_MOSEPH) so no ephemeris data files are
required. To switch to the full Swiss Ephemeris files later, set an ephe path
via ``configure_ephe_path`` and change the base flag to ``FLG_SWIEPH``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import swisseph as swe

from core.constants import AYANAMSHA_MODES, SWE_PLANET

# Base calculation flags. Moshier = no data files needed; sidereal + speed always.
_BASE_FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

_EPHE_MODE = "moshier"


def configure_ephe_path(path: str | None) -> None:
    """Point Swiss Ephemeris at data files. If given and present, use SWIEPH."""
    global _BASE_FLAGS, _EPHE_MODE
    if path and os.path.isdir(path):
        swe.set_ephe_path(path)
        _BASE_FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        _EPHE_MODE = "swieph"


def ephe_mode() -> str:
    return _EPHE_MODE


def swe_version() -> str:
    return swe.version


def set_sidereal_mode(ayanamsha: str) -> None:
    """Apply the sidereal (ayanamsha) mode globally in Swiss Ephemeris.

    Public because callers using ``swe`` directly (e.g. house computation) must
    ensure the sidereal frame is set before their call.
    """
    try:
        swe.set_sid_mode(AYANAMSHA_MODES[ayanamsha])
    except KeyError:
        raise ValueError(f"unknown ayanamsha: {ayanamsha!r}") from None


# Backwards-compatible private alias used within this module.
_set_ayanamsha = set_sidereal_mode


def julian_day(dt_utc: datetime) -> float:
    """Julian day (UT) for a timezone-aware UTC datetime."""
    if dt_utc.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC)")
    dt = dt_utc.astimezone(timezone.utc)
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0 + dt.microsecond / 3.6e9
    return swe.julday(dt.year, dt.month, dt.day, hour)


def get_ayanamsha(jd: float, ayanamsha: str) -> float:
    """Ayanamsha value in degrees at the given Julian day."""
    _set_ayanamsha(ayanamsha)
    return swe.get_ayanamsa_ut(jd)


def sidereal_longitude(jd: float, swe_planet_id: int, ayanamsha: str) -> tuple[float, float]:
    """Return (sidereal ecliptic longitude, longitude speed deg/day)."""
    _set_ayanamsha(ayanamsha)
    values, _retflag = swe.calc_ut(jd, swe_planet_id, _BASE_FLAGS)
    return values[0], values[3]
