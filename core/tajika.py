"""Tajika (Varshaphal): the annual chart for one year of life, read in code.

1. Varsha Pravesh: the moment the Sun returns to its exact birth longitude (sidereal, in the birth chart's own
   ayanamsha, so the ayanamsha cancels out), cast for the birthplace.
2. Muntha: the birth Lagna sign advanced one sign per completed year; read by its house from the annual Lagna.
3. Year lord (Varshesha) from the five office-bearers (Pancha-adhikari): birth Lagna lord, annual Lagna lord,
   Muntha lord, Tri-rashi lord, and the lord of the Sun's sign (day return) or the Moon's sign (night return).
   The year lord is the strongest office-bearer that aspects the annual Lagna (Tajika aspect); if none aspects,
   the strongest of all. Strength here is the planet's dignity in the annual chart (exalted > own > friendly >
   neutral > enemy > debilitated); ties go to the earlier office in the list above. The classical full
   Pancha-vargeeya bala is not used yet.
4. Tajika aspects among the seven planets, counted by sign: 3/11 and 5/9 friendly, 4/10 and 1/7 inimical, 2/12 and
   6/8 none. An aspect is "within orbs" (deeptamsha) when the planets' separation is within the average of their
   orbs of the exact angle.
5. Mudda dasha: Vimshottari compressed into the year (from this Varsha Pravesh to the next). It starts with the lord
   of the birth nakshatra moved on one nakshatra per completed year, with the same part already run as at birth;
   the sequence then runs all nine lords and closes with the rest of the first.
6. Sahams: sensitive points A - B + C (B - A + C for a night return where the saham reverses); 30° is added when C
   does not fall between B and A counting forward from B (the classical exception). Each is read by its house and
   its lord. Death and illness-of-others sahams are left out.
7. Tajika yogas (the eight that follow from positions alone): Ikkabala, Induvara, Ithasala, Ishrafa, Nakta,
   Yamaya, Kamboola and Radda. Ithasala: two planets in a Tajika aspect within orbs, the faster one behind the
   slower in degrees (applying); Ishrafa: the faster one already past (separating); Nakta: a faster third planet in
   Ithasala with two that are not; Yamaya: the same through a slower third; Kamboola: the Moon in Ithasala with one
   of an Ithasala pair; Radda: an Ithasala spoiled by a retrograde, combust or debilitated planet. Manau, Khallasara,
   Dutthottha-davira, Tambira, Kuttha, Durapha, Gairi-kamboola and Duhphali-kuttha are not computed yet.
Rahu and Ketu take no part in Tajika aspects or office. Schools differ on the Tri-rashi table and the orbs; both are
constants below.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from core import constants as C
from core.dignity import dignity
from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.panchang import _jd_to_utc, compute_panchang

SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
SIDEREAL_YEAR = 365.256363
# Tri-rashi lords by the annual Lagna sign: (day return, night return). Tajika Neelakanthi as commonly printed.
TRI_RASHI = [("Sun", "Jupiter"), ("Venus", "Moon"), ("Saturn", "Mercury"), ("Venus", "Mars"), ("Jupiter", "Sun"),
             ("Moon", "Venus"), ("Mercury", "Saturn"), ("Mars", "Venus"), ("Saturn", "Saturn"), ("Mars", "Mars"),
             ("Jupiter", "Jupiter"), ("Moon", "Moon")]
# Deeptamsha (orbs) in degrees.
ORBS = {"Sun": 15, "Moon": 12, "Mars": 8, "Mercury": 7, "Jupiter": 9, "Venus": 7, "Saturn": 9}
ASPECTS = {1: ("conjunction", "inimical", 0), 7: ("opposition", "inimical", 180), 4: ("square", "inimical", 90),
           10: ("square", "inimical", 90), 3: ("sextile", "friendly", 60), 11: ("sextile", "friendly", 60),
           5: ("trine", "friendly", 120), 9: ("trine", "friendly", 120)}
STRENGTH = {"exalted": 5, "own": 4, "friendly": 3, "neutral": 2, "enemy": 1, "debilitated": 0}
# (name, A, B, C, reverses at night, what it shows)
SAHAMS = [("Punya", "Moon", "Sun", "Asc", True, "fortune and good deeds"),
          ("Vidya", "Sun", "Moon", "Asc", True, "learning and studies"),
          ("Yasas", "Jupiter", "Punya", "Asc", True, "fame and recognition"),
          ("Mitra", "Jupiter", "Punya", "Venus", True, "friends and helpers"),
          ("Mahatmya", "Punya", "Mars", "Asc", True, "honour and standing"),
          ("Asha", "Saturn", "Venus", "Asc", True, "hopes and wishes"),
          ("Bhratri", "Jupiter", "Saturn", "Asc", False, "brothers and sisters"),
          ("Gaurava", "Jupiter", "Moon", "Sun", True, "respect"),
          ("Pitri", "Saturn", "Sun", "Asc", True, "father and authority"),
          ("Matri", "Moon", "Venus", "Asc", True, "mother"),
          ("Putra", "Jupiter", "Moon", "Asc", True, "children"),
          ("Jeeva", "Saturn", "Jupiter", "Asc", True, "livelihood"),
          ("Karma", "Mars", "Mercury", "Asc", True, "work and action"),
          ("Vanik", "Moon", "Mercury", "Asc", True, "trade and business"),
          ("Kali", "Jupiter", "Mars", "Asc", True, "disputes"),
          ("Vivaha", "Venus", "Saturn", "Asc", False, "marriage")]
OFFICES = ["Birth Lagna lord", "Annual Lagna lord", "Muntha lord", "Tri-rashi lord", "Sun or Moon sign lord"]


def _sign_dist(a: int, b: int) -> int:
    """Signs from a to b, counting both (1 = same sign)."""
    return (b - a) % 12 + 1


def _sun(jd: float, ayanamsha: str) -> tuple[float, float]:
    g = compute_grahas(jd, ayanamsha)["Sun"]
    return g.longitude, g.speed


def varsha_pravesh(birth_utc: datetime, sun_lon: float, years: int, ayanamsha: str) -> datetime:
    """The UTC moment the sidereal Sun returns to ``sun_lon`` ``years`` years after birth."""
    jd = julian_day(birth_utc) + years * SIDEREAL_YEAR
    for _ in range(8):
        lon, speed = _sun(jd, ayanamsha)
        jd -= ((lon - sun_lon + 180) % 360 - 180) / speed
    return _jd_to_utc(jd)


def _birth_utc(request: dict) -> datetime:
    tob = time.fromisoformat(request["tob"])
    return datetime.combine(date.fromisoformat(request["dob"]), tob, tzinfo=ZoneInfo(request["tz_name"])).astimezone(timezone.utc)


def tajika_aspect(a: dict, b: dict) -> dict | None:
    """The Tajika aspect between two planets (dicts with sign_index, longitude, name), or None."""
    d = _sign_dist(a["sign_index"], b["sign_index"])
    if d not in ASPECTS:
        return None
    kind, nature, angle = ASPECTS[d]
    sep = abs((b["longitude"] - a["longitude"] + 180) % 360 - 180)
    orb = (ORBS[a["name"]] + ORBS[b["name"]]) / 2
    return {"kind": kind, "nature": nature, "within_orbs": abs(sep - angle) <= orb, "off_by": round(abs(sep - angle), 2)}


def saham(a: float, b: float, c: float) -> float:
    """A - B + C, adding 30° when C is not between B and A (counted forward from B)."""
    lon = (a - b + c) % 360
    if not (c - b) % 360 < (a - b) % 360:
        lon = (lon + 30) % 360
    return lon


def sahams(points: dict, day: bool, lagna: int, planets: dict) -> list[dict]:
    pts, out = dict(points), []
    for name, a, b, c, rev, shows in SAHAMS:
        x, y = (a, b) if day or not rev else (b, a)
        lon = saham(pts[x], pts[y], pts[c])
        pts[name] = lon
        sign = int(lon // 30)
        lord = C.SIGN_LORDS[sign]
        out.append({"name": name, "shows": shows, "longitude": round(lon, 4), "sign": C.SIGNS[sign],
                    "deg": round(lon % 30, 2), "house": _sign_dist(lagna, sign), "lord": lord,
                    "lord_dignity": planets[lord]["dignity"], "lord_house": planets[lord]["house"],
                    "formula": f"{x} - {y} + {c}"})
    return out


def _ithasala(a: dict, b: dict) -> str | None:
    """'ithasala' (applying), 'ishrafa' (separating) or None, for two planets in a Tajika aspect within orbs."""
    asp = tajika_aspect(a, b)
    if not asp or not asp["within_orbs"]:
        return None
    fast, slow = (a, b) if abs(a["speed"]) > abs(b["speed"]) else (b, a)
    return "ithasala" if fast["longitude"] % 30 < slow["longitude"] % 30 else "ishrafa"


def yogas(planets: dict) -> list[dict]:
    P = {n: planets[n] for n in SEVEN}
    out = []
    houses = [p["house"] for p in P.values()]
    if all(h in (1, 2, 4, 5, 7, 8, 10, 11) for h in houses):
        out.append({"yoga": "Ikkabala", "good": True, "planets": SEVEN,
                    "text": "All seven planets are in angles or succeedent houses: a strong, supportive year."})
    elif all(h in (3, 6, 9, 12) for h in houses):
        out.append({"yoga": "Induvara", "good": False, "planets": SEVEN,
                    "text": "All seven planets are in cadent houses (3, 6, 9, 12): a weak year that needs effort."})
    rel = {}
    for i, a in enumerate(SEVEN):
        for b in SEVEN[i + 1:]:
            rel[(a, b)] = rel[(b, a)] = _ithasala(P[a], P[b])
    spoiled = lambda n: P[n]["retrograde"] or P[n]["combust"] or P[n]["dignity"] == "debilitated"
    for i, a in enumerate(SEVEN):
        for b in SEVEN[i + 1:]:
            r = rel[(a, b)]
            if r == "ithasala":
                bad = [n for n in (a, b) if spoiled(n)]
                if bad:
                    out.append({"yoga": "Radda", "good": False, "planets": [a, b],
                                "text": f"{a} and {b} apply to each other (Ithasala), but {', '.join(bad)} "
                                        f"{'is' if len(bad) == 1 else 'are'} retrograde, combust or debilitated: "
                                        "the promise is spoiled."})
                else:
                    out.append({"yoga": "Ithasala", "good": True, "planets": [a, b],
                                "text": f"{a} and {b} apply to each other within orbs: their matters come together."})
                if "Moon" not in (a, b) and not bad and not spoiled("Moon"):  # a spoiled pair or Moon cannot help
                    m = [x for x in (a, b) if rel[("Moon", x)] == "ithasala"]
                    if m:
                        out.append({"yoga": "Kamboola", "good": True, "planets": ["Moon", a, b],
                                    "text": f"The Moon applies to {m[0]} as well: the {a}–{b} link is strengthened."})
            elif r == "ishrafa":
                out.append({"yoga": "Ishrafa", "good": False, "planets": [a, b],
                            "text": f"{a} and {b} are separating (Ishrafa): the matter has passed or slips away."})
            else:
                for c in SEVEN:
                    if c in (a, b) or rel[(c, a)] != "ithasala" or rel[(c, b)] != "ithasala":
                        continue
                    faster = abs(P[c]["speed"]) > max(abs(P[a]["speed"]), abs(P[b]["speed"]))
                    slower = abs(P[c]["speed"]) < min(abs(P[a]["speed"]), abs(P[b]["speed"]))
                    if faster or slower:
                        y = "Nakta" if faster else "Yamaya"
                        out.append({"yoga": y, "good": True, "planets": [a, b, c],
                                    "text": f"{a} and {b} do not meet directly, but the {'faster' if faster else 'slower'} "
                                            f"{c} links them ({y}): the matter succeeds through another person."})
    return out


def mudda_dasha(start: datetime, end: datetime, moon_lon: float, years: int) -> list[dict]:
    nak = int(moon_lon // C.NAKSHATRA_ARC)
    done = (moon_lon % C.NAKSHATRA_ARC) / C.NAKSHATRA_ARC        # the part of the first period already run at birth
    first = C.NAKSHATRA_LORDS[(nak + years) % 27]
    i0 = C.VIMSOTTARI_ORDER.index(first)
    span = end - start
    share = lambda lord: span * (C.VIMSOTTARI_YEARS[lord] / C.VIMSOTTARI_TOTAL_YEARS)
    parts = [(first, share(first) * (1 - done))]
    parts += [(C.VIMSOTTARI_ORDER[(i0 + k) % 9], share(C.VIMSOTTARI_ORDER[(i0 + k) % 9])) for k in range(1, 9)]
    if done > 0:
        parts.append((first, share(first) * done))
    out, t = [], start
    for lord, length in parts:
        out.append({"lord": lord, "start": t.isoformat(), "end": (t + length).isoformat()})
        t += length
    out[-1]["end"] = end.isoformat()  # exactly the next Varsha Pravesh (no rounding drift)
    return out


def annual(chart: dict, request: dict, years: int) -> dict:
    """The Varshaphal for the year that begins ``years`` completed years after birth (0 = the birth year)."""
    if not 0 <= years <= 120:
        raise ValueError("the year must be within 120 years of birth")
    ayan = chart["meta"]["ayanamsha"]
    lat, lon, tz = request["lat"], request["lon"], request["tz_name"]
    natal_sun = chart["grahas"]["Sun"]["longitude"]
    birth = _birth_utc(request)
    vp = varsha_pravesh(birth, natal_sun, years, ayan)
    nxt = varsha_pravesh(birth, natal_sun, years + 1, ayan)
    jd = julian_day(vp)
    g = compute_grahas(jd, ayan, node_type=chart["meta"].get("node_type", "mean"))
    asc = compute_houses(jd, lat, lon, ayan).ascendant
    L = int(asc // 30)
    local = vp.astimezone(ZoneInfo(tz))
    p = compute_panchang(local.date(), lat, lon, tz)
    day = p.sunrise <= vp < p.sunset

    planets = {n: {"name": n, "longitude": round(x.longitude, 4), "sign_index": x.sign_index, "sign": x.sign,
                   "deg": round(x.longitude % 30, 2), "house": _sign_dist(L, x.sign_index), "retrograde": x.retrograde,
                   "nakshatra": x.nakshatra, "dignity": dignity(n, x.sign_index), "speed": round(x.speed, 4),
                   "combust": x.combust} for n, x in g.items()}
    natal_lagna = chart["lagna"]["sign_index"]
    muntha = (natal_lagna + years) % 12
    officers = [C.SIGN_LORDS[natal_lagna], C.SIGN_LORDS[L], C.SIGN_LORDS[muntha], TRI_RASHI[L][0 if day else 1],
                C.SIGN_LORDS[planets["Sun" if day else "Moon"]["sign_index"]]]
    board = []
    for office, planet in zip(OFFICES, officers):
        x = planets[planet]
        d = _sign_dist(x["sign_index"], L)
        board.append({"office": office, "planet": planet, "dignity": x["dignity"], "strength": STRENGTH[x["dignity"]],
                      "aspects_lagna": d in ASPECTS, "aspect": ASPECTS[d][0] if d in ASPECTS else None})
    pool = [b for b in board if b["aspects_lagna"]] or board
    best = max(b["strength"] for b in pool)
    lord = next(b for b in pool if b["strength"] == best)
    why = (f"{lord['planet']} ({lord['office'].lower()}) is the strongest office-bearer ({lord['dignity']}) "
           + ("that aspects the annual Lagna" if any(b["aspects_lagna"] for b in board)
              else "(none of them aspects the annual Lagna)") + ".")

    aspects = []
    for i, a in enumerate(SEVEN):
        for b in SEVEN[i + 1:]:
            x = tajika_aspect(planets[a], planets[b])
            if x:
                aspects.append({"a": a, "b": b, **x})

    return {
        "years": years, "age": years, "varsha_pravesh": vp.isoformat(), "local": local.isoformat(), "tz": tz,
        "next": nxt.isoformat(), "day": day, "ayanamsha": ayan,
        "lagna": {"sign_index": L, "sign": C.SIGNS[L], "deg": round(asc % 30, 2), "longitude": round(asc, 4)},
        "planets": planets,
        "muntha": {"sign_index": muntha, "sign": C.SIGNS[muntha], "house": _sign_dist(L, muntha),
                   "lord": C.SIGN_LORDS[muntha]},
        "office_bearers": board, "year_lord": {"planet": lord["planet"], "office": lord["office"], "why": why},
        "aspects": aspects,
        "sahams": sahams({**{n: planets[n]["longitude"] for n in SEVEN}, "Asc": asc}, day, L, planets),
        "yogas": yogas(planets),
        "mudda_dasha": mudda_dasha(vp, nxt, chart["grahas"]["Moon"]["longitude"], years),
    }


def years_for(request: dict, on: date) -> int:
    """Completed years at ``on`` by the calendar birthday (the Varsha Pravesh falls within a day or so of it)."""
    b = date.fromisoformat(request["dob"])
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))
