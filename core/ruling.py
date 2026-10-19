"""KP Ruling Planets (RP) for any moment and place.

In order of strength (the usual KP order): the Lagna star lord, the Lagna sign lord, the Moon star lord, the Moon
sign lord and the day lord. The Lagna and Moon sub lords are given too. Rahu and Ketu join the ruling planets when
they stand in a sign ruled by one of them (they act as agents of that lord). The day runs from sunrise to sunrise,
so the day lord is the lord of the weekday of the last sunrise at the place (found from the longitude, so no time
zone is needed). Lagna by Placidus with the KP ayanamsha, as in the rest of the KP tools.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import swisseph as swe

from core.constants import NAKSHATRA_ARC, NAKSHATRAS, SIGN_LORDS, SIGNS
from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.kp import kp_lords
from core.panchang import _jd_to_utc

DAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Sunday first
ROLES = ["Lagna star lord", "Lagna sign lord", "Moon star lord", "Moon sign lord", "Day lord"]


def last_sunrise(jd: float, lat: float, lon: float) -> float:
    rise = swe.rise_trans(jd - 1.0, swe.SUN, swe.CALC_RISE, (lon, lat, 0.0), 0.0, 0.0, swe.FLG_MOSEPH)[1][0]
    nxt = swe.rise_trans(rise + 0.01, swe.SUN, swe.CALC_RISE, (lon, lat, 0.0), 0.0, 0.0, swe.FLG_MOSEPH)[1][0]
    return nxt if nxt <= jd else rise


def day_lord(when: datetime, lat: float, lon: float) -> str:
    """The lord of the Vedic day (sunrise to sunrise) at ``when`` (timezone-aware)."""
    rise = _jd_to_utc(last_sunrise(julian_day(when), lat, lon)) + timedelta(hours=lon / 15)  # local mean time
    return DAY_LORD[(rise.weekday() + 1) % 7]


def ruling_planets(when: datetime, lat: float, lon: float, ayanamsha: str = "krishnamurti",
                   node_type: str = "mean") -> dict:
    if when.tzinfo is None:
        raise ValueError("the time needs a timezone")
    jd = julian_day(when)
    asc = compute_houses(jd, lat, lon, ayanamsha).ascendant
    g = compute_grahas(jd, ayanamsha, node_type=node_type)
    a, m = kp_lords(asc), kp_lords(g["Moon"].longitude)
    rows = [{"role": r, "planet": p} for r, p in zip(ROLES, [a.star_lord, a.sign_lord, m.star_lord, m.sign_lord,
                                                              day_lord(when, lat, lon)])]
    rps = list(dict.fromkeys(r["planet"] for r in rows))
    nodes = [n for n in ("Rahu", "Ketu") if SIGN_LORDS[g[n].sign_index] in rps]
    return {"at": when.isoformat(), "rows": rows, "ruling_planets": rps + nodes,
            "nodes": [{"planet": n, "sign": SIGNS[g[n].sign_index], "for": SIGN_LORDS[g[n].sign_index]} for n in nodes],
            "lagna": {"longitude": round(asc, 4), "sign": SIGNS[int(asc // 30)], "star": NAKSHATRAS[int(asc // NAKSHATRA_ARC)],
                      "sub_lord": a.sub_lord},
            "moon": {"longitude": round(g["Moon"].longitude, 4), "sign": g["Moon"].sign, "star": NAKSHATRAS[int(g["Moon"].longitude // NAKSHATRA_ARC)],
                     "sub_lord": m.sub_lord}}
