"""Birth summary (Avakhada chakra), special points, and when each lagna rises in a day.

Avakhada: the one-table summary astrologers expect first (lagna, rashi and nakshatra with their lords, varna,
vashya, yoni, gana, nadi, paya, element, naming letter, and the tithi, yoga and karana at birth).
Special points: Bhrigu Bindu, Indu Lagna, Bhava / Hora / Ghati Lagna, Mandi and Gulika, and the planets in a
Pushkara navamsha. All are worked out in the chart's own ayanamsha.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from app.panchang_extra import NAMING, tithi_name
from core import constants as C
from core import matchmaking as M
from core.ephemeris import julian_day, sidereal_longitude
from core.houses import compute_houses
from core.panchang import compute_panchang

ELEMENT = ["Fire", "Earth", "Air", "Water"]
PAYA = {1: "Gold (Swarna)", 6: "Gold (Swarna)", 11: "Gold (Swarna)", 2: "Silver (Rajat)", 5: "Silver (Rajat)",
        9: "Silver (Rajat)", 3: "Copper (Tamra)", 7: "Copper (Tamra)", 10: "Copper (Tamra)", 4: "Iron (Loha)",
        8: "Iron (Loha)", 12: "Iron (Loha)"}  # by the Moon's house from the lagna
KALA = {"Sun": 30, "Moon": 16, "Mars": 6, "Mercury": 8, "Jupiter": 10, "Venus": 12, "Saturn": 1}
# Pushkara navamsha: which ninth of a sign, by the sign's element (fire, earth, air, water).
PUSHKARA_NAV = {0: (7, 9), 1: (3, 5), 2: (6, 8), 3: (1, 3)}
# Mandi rises this many ghatis (of 30) into the day or night; Gulika rules this eighth of it (Sunday = 0).
MANDI_GHATI_DAY = {0: 26, 1: 22, 2: 18, 3: 14, 4: 10, 5: 6, 6: 2}
MANDI_GHATI_NIGHT = {0: 10, 1: 6, 2: 2, 3: 26, 4: 22, 5: 18, 6: 14}
GULIKA_PART_DAY = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
GULIKA_PART_NIGHT = {0: 3, 1: 2, 2: 1, 3: 7, 4: 6, 5: 5, 6: 4}
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _point(lon: float, lagna_sign: int, name: str, meaning: str) -> dict:
    lon %= 360
    s = int(lon // 30)
    nak = int(lon // (360 / 27))
    return {"name": name, "longitude": round(lon, 3), "sign": C.SIGNS[s], "sign_index": s,
            "degrees_in_sign": round(lon % 30, 3), "house": (s - lagna_sign) % 12 + 1,
            "nakshatra": C.NAKSHATRAS[nak], "meaning": meaning}


def _birth(request: dict) -> tuple[datetime, ZoneInfo]:
    tz = ZoneInfo(request["tz_name"])
    return datetime.fromisoformat(f"{request['dob']}T{request['tob'][:8]}").replace(tzinfo=tz), tz


def _day_of_birth(request: dict):
    """The Vedic day the birth falls in (sunrise to sunrise), with its sunrise, sunset and next sunrise."""
    born, tz = _birth(request)
    p = compute_panchang(born.date(), request["lat"], request["lon"], request["tz_name"])
    if born < p.sunrise:
        p = compute_panchang(born.date() - timedelta(days=1), request["lat"], request["lon"], request["tz_name"])
    nxt = compute_panchang(p.date + timedelta(days=1), request["lat"], request["lon"], request["tz_name"])
    return born, p, nxt


def avakhada(chart: dict, request: dict) -> dict:
    g, L = chart["grahas"], chart["lagna"]
    moon = g["Moon"]
    s, m = g["Sun"]["longitude"], moon["longitude"]
    e = (m - s) % 360
    nak = moon["nakshatra_index"]
    born, p, _ = _day_of_birth(request)
    moon_house = (moon["sign_index"] - L["sign_index"]) % 12 + 1
    rows = [
        ("Lagna", f"{L['sign']} · lord {C.SIGN_LORDS[L['sign_index']]}"),
        ("Rashi (Moon sign)", f"{moon['sign']} · lord {C.SIGN_LORDS[moon['sign_index']]}"),
        ("Nakshatra", f"{moon['nakshatra']} pada {moon['pada']} · lord {C.NAKSHATRA_LORDS[nak]}"),
        ("Naming letter", NAMING[nak].split()[moon["pada"] - 1]),
        ("Varna", M.VARNA_BY_SIGN[moon["sign_index"]]),
        ("Vashya", M.vashya_group(moon["sign_index"], moon["degrees_in_sign"])),
        ("Yoni", M.YONI_BY_NAKSHATRA[nak]),
        ("Gana", M.GANA_BY_NAKSHATRA[nak]),
        ("Nadi", M.NADI_BY_NAKSHATRA[nak]),
        ("Paya", PAYA[moon_house]),
        ("Element (tatva)", ELEMENT[moon["sign_index"] % 4]),
        ("Birth day (Vedic)", WEEKDAYS[(p.date.weekday() + 1) % 7] + (" (born before sunrise)" if born.date() != p.date else "")),
        ("Tithi at birth", tithi_name(int(e // 12) + 1)),
        ("Yoga at birth", C.YOGAS[int(((s + m) % 360) // (360 / 27))]),
        ("Karana at birth", C.karana_name(int(e // 6))),
        ("Ayanamsha", f"{chart['meta'].get('ayanamsha', '').title()} · {chart['meta'].get('ayanamsha_value', 0):.4f}°"),
    ]
    return {"rows": [{"label": a, "value": b} for a, b in rows]}


def _asc(when: datetime, lat: float, lon: float, ay: str) -> float:
    return compute_houses(julian_day(when.astimezone(timezone.utc)), lat, lon, ay).ascendant


def special_points(chart: dict, request: dict) -> dict:
    g, L = chart["grahas"], chart["lagna"]["sign_index"]
    ay = chart["meta"].get("ayanamsha", "krishnamurti")
    lat, lon = request["lat"], request["lon"]
    born, p, nxt = _day_of_birth(request)
    pts = []
    # Bhrigu Bindu: halfway from Rahu forward to the Moon.
    rahu, moon = g["Rahu"]["longitude"], g["Moon"]["longitude"]
    pts.append(_point(rahu + ((moon - rahu) % 360) / 2, L, "Bhrigu Bindu",
                      "A sensitive point of destiny; transits over it tend to switch on events."))
    # Indu Lagna: the kalas of the 9th lords from the Lagna and from the Moon, counted from the Moon.
    ninth = lambda s: C.SIGN_LORDS[(s + 8) % 12]
    k = (KALA[ninth(L)] + KALA[ninth(g["Moon"]["sign_index"])]) % 12 or 12
    s_idx = (g["Moon"]["sign_index"] + k - 1) % 12
    pts.append({**_point(s_idx * 30 + 15, L, "Indu Lagna", "The lagna of wealth: planets with it or aspecting it "
                         "show how money comes."), "degrees_in_sign": None, "nakshatra": None})
    # Bhava, Hora and Ghati Lagna: from the Sun at sunrise, moving 1 sign per 2 hours, per hour, per ghati.
    sun_sr, _ = sidereal_longitude(julian_day(p.sunrise.astimezone(timezone.utc)), swe.SUN, ay)
    mins = (born - p.sunrise).total_seconds() / 60
    for name, speed, meaning in (("Bhava Lagna", 0.25, "Read for overall health and the self, beside the Lagna."),
                                 ("Hora Lagna", 0.5, "Read for wealth and prosperity."),
                                 ("Ghati Lagna", 1.25, "Read for power, status and authority.")):
        pts.append(_point(sun_sr + speed * mins, L, name, meaning))
    # Mandi and Gulika (Prashna Marga): the degree rising when Mandi rises / when Saturn's eighth begins.
    day = p.sunrise <= born < p.sunset
    start, end = (p.sunrise, p.sunset) if day else (p.sunset, nxt.sunrise)
    wd = (p.date.weekday() + 1) % 7
    mandi_t = start + (end - start) * (MANDI_GHATI_DAY if day else MANDI_GHATI_NIGHT)[wd] / 30
    gulika_t = start + (end - start) * ((GULIKA_PART_DAY if day else GULIKA_PART_NIGHT)[wd] - 1) / 8
    pts.append(_point(_asc(mandi_t, lat, lon, ay), L, "Mandi", "A point to take care around; its house asks for patience."))
    pts.append(_point(_asc(gulika_t, lat, lon, ay), L, "Gulika", "Saturn's sub-point; its house asks for steady effort."))
    # Planets in a Pushkara navamsha (an especially nourishing ninth of a sign).
    push = [n for n, x in g.items() if int(x["degrees_in_sign"] // (30 / 9)) + 1 in PUSHKARA_NAV[x["sign_index"] % 4]]
    return {"points": pts, "pushkara": push}


def lagna_times(day: date, lat: float, lon: float, tz_name: str, ay: str = "krishnamurti") -> list[dict]:
    """When each sign rises on this local day: [{sign, start, end}] (local HH:MM), found to the minute."""
    tz = ZoneInfo(tz_name)
    t0 = datetime(day.year, day.month, day.day, tzinfo=tz)
    sign_at = lambda t: int(_asc(t, lat, lon, ay) // 30)
    out, cur, cur_start, t = [], sign_at(t0), t0, t0
    while t < t0 + timedelta(days=1):
        nxt = t + timedelta(minutes=10)
        if sign_at(nxt) != cur:
            lo, hi = t, nxt
            while (hi - lo).total_seconds() > 30:
                mid = lo + (hi - lo) / 2
                lo, hi = (mid, hi) if sign_at(mid) == cur else (lo, mid)
            out.append({"sign": C.SIGNS[cur], "start": cur_start.strftime("%H:%M"), "end": hi.strftime("%H:%M")})
            cur, cur_start = sign_at(hi), hi
        t = nxt
    out.append({"sign": C.SIGNS[cur], "start": cur_start.strftime("%H:%M"), "end": "24:00"})
    return out
