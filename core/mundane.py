"""Mundane (Samhita) year charts: the Hindu New Year and Mesha Sankranti, with the year's king and minister.

- Mesha Sankranti: the moment the sidereal Sun (Lahiri) enters Aries.
- Hindu New Year (Chaitra Shukla Pratipada, Vikram Samvat): the new moon that begins Chaitra, the last new moon
  before Mesha Sankranti (so an Adhik Chaitra is skipped). The chart is cast for that new moon.
- Raja (king) of the year: the lord of the weekday on which Chaitra Shukla Pratipada falls: the first local
  sunrise after the new moon if Pratipada still holds then, else (a kshaya Pratipada that touches no sunrise) the
  day on which it began. 2026 is such a year: Ugadi on Thursday 19 March, Raja Jupiter.
  Mantri (minister): the lord of the weekday (sunrise to sunrise) of Mesha Sankranti.
- Samvatsara: the name in the 60-year Jovian cycle, as on the Muhurat screen.
Both charts are cast for the chosen place, Lahiri, whole-sign houses from the Lagna.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import swisseph as swe

from app.panchang_extra import SAMVATSARA
from core import constants as C
from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.panchang import _jd_to_utc
from core.ruling import day_lord

AYAN = "lahiri"
SYNODIC = 29.530589


def _sun_moon(jd: float) -> tuple[float, float]:
    g = compute_grahas(jd, AYAN)
    return g["Sun"].longitude, g["Moon"].longitude


def mesha_sankranti(year: int) -> datetime:
    jd = julian_day(datetime(year, 4, 14, tzinfo=timezone.utc))
    for _ in range(8):
        g = compute_grahas(jd, AYAN)["Sun"]
        jd -= ((g.longitude + 180) % 360 - 180) / g.speed
    return _jd_to_utc(jd)


def new_year(year: int) -> datetime:
    """The new moon that starts Chaitra: the last one before Mesha Sankranti."""
    ms = julian_day(mesha_sankranti(year))
    s, m = _sun_moon(ms)
    t = ms - ((m - s) % 360) / (360 / SYNODIC)
    for _ in range(6):
        s, m = _sun_moon(t)
        t -= (((m - s) + 180) % 360 - 180) / (360 / SYNODIC - 360 / 365.25)
    return _jd_to_utc(t)


def _chart(when: datetime, lat: float, lon: float) -> dict:
    jd = julian_day(when)
    asc = compute_houses(jd, lat, lon, AYAN).ascendant
    L = int(asc // 30)
    g = compute_grahas(jd, AYAN)
    return {"at": when.isoformat(), "lagna": {"sign_index": L, "sign": C.SIGNS[L], "deg": round(asc % 30, 2)},
            "planets": {n: {"sign_index": x.sign_index, "sign": x.sign, "deg": round(x.longitude % 30, 2),
                            "house": (x.sign_index - L) % 12 + 1, "retrograde": x.retrograde} for n, x in g.items()}}


def year_charts(year: int, lat: float, lon: float) -> dict:
    nm, ms = new_year(year), mesha_sankranti(year)
    rise = swe.rise_trans(julian_day(nm), swe.SUN, swe.CALC_RISE, (lon, lat, 0.0), 0.0, 0.0, swe.FLG_MOSEPH)[1][0]
    sun, moon = _sun_moon(rise)
    if (moon - sun) % 360 < 12:      # Pratipada holds at the first sunrise after the new moon: that is the day
        day = _jd_to_utc(rise) + timedelta(minutes=1)
    else:                            # it ended before that sunrise (kshaya): the day it began, as in the panchang
        day = nm
    raja = day_lord(day, lat, lon)
    mantri = day_lord(ms, lat, lon)
    return {"year": year, "samvatsara": SAMVATSARA[(year - 1987) % 60], "vikram_samvat": year + 57,
            "new_year": {**_chart(nm, lat, lon), "pratipada_day": day.isoformat()},
            "mesha_sankranti": _chart(ms, lat, lon),
            "raja": raja, "mantri": mantri}
