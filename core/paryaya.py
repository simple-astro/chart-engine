"""Paryaya (Nadi transit rounds): when transiting Jupiter and Saturn cross the exact degree of a natal planet or the
Lagna. Each slow planet goes round the zodiac in about 12 (Jupiter) and 29½ (Saturn) years, touching every natal
point once per round, or three times when it turns retrograde over it.

Crossings are found by stepping a day at a time and refining to the minute. Positions are sidereal in the birth
chart's own ayanamsha. This is a timing hint only: scripts/backtest_paryaya.py measures it against dated events, and
no verdict uses it unless that backtest supports it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas

TRANSITING = ["Jupiter", "Saturn"]
POINTS = ["Lagna", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def _lon(planet: str, jd: float, ayanamsha: str) -> tuple[float, float]:
    g = compute_grahas(jd, ayanamsha)[planet]
    return g.longitude, g.speed


def natal_points(chart: dict) -> dict:
    pts = {p: chart["grahas"][p]["longitude"] for p in POINTS if p != "Lagna"}
    pts["Lagna"] = chart["lagna"]["ascendant"]
    return pts


def crossings(chart: dict, start: date, end: date, transiting=TRANSITING) -> list[dict]:
    ayan = chart["meta"]["ayanamsha"]
    pts = natal_points(chart)
    jd0 = julian_day(datetime(start.year, start.month, start.day, tzinfo=timezone.utc))
    days = (end - start).days
    out = []
    for planet in transiting:
        lons = [_lon(planet, jd0 + d, ayan)[0] for d in range(days + 1)]
        for point, target in pts.items():
            diff = lambda lon: (lon - target + 180) % 360 - 180
            for d in range(days):
                a, b = diff(lons[d]), diff(lons[d + 1])
                if a == 0 or (a < 0) != (b < 0) and abs(a - b) < 180:
                    lo, hi = jd0 + d, jd0 + d + 1
                    for _ in range(20):  # to about a minute
                        mid = (lo + hi) / 2
                        if (diff(_lon(planet, lo, ayan)[0]) < 0) == (diff(_lon(planet, mid, ayan)[0]) < 0):
                            lo = mid
                        else:
                            hi = mid
                    when = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=hi - 2451545.0)
                    out.append({"planet": planet, "point": point, "date": when.date().isoformat(),
                                "retrograde": _lon(planet, hi, ayan)[1] < 0})
    return sorted(out, key=lambda x: (x["date"], x["planet"], x["point"]))
