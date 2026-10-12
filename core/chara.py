"""Jaimini Chara Dasha (K.N. Rao's counting): twelve sign periods starting from the Lagna.

- Order: from the Lagna sign. If the 9th sign from the Lagna is in the odd-footed (Vishamapada) group
  Aries, Taurus, Gemini, Libra, Scorpio, Sagittarius, the signs follow in zodiac order; otherwise (Cancer, Leo,
  Virgo, Capricorn, Aquarius, Pisces) in reverse order.
- Years of a sign: count from the sign to the sign where its lord stands, inclusive — forward for a
  Vishamapada sign, backward for a Samapada sign — minus 1. A lord in its own sign gives 12 years.
  Scorpio (Mars / Ketu) and Aquarius (Saturn / Rahu): if one lord stands in the sign itself, count to the other;
  if both are outside, to the stronger (more planets with it, then the higher degree). No years are added for
  exaltation or debilitation (K.N. Rao).
- Sub-periods: twelve of one twelfth each (one month per year of the main period), the main sign itself last: a
  Vishamapada sign starts from its 2nd sign going forward, a Samapada sign from its 12th going backward.
- After the first twelve periods the cycle repeats with each sign lasting (12 - years).
Years are 365.25 days, as in the other dasha engines. Shown beside Vimshottari for reflection; it does not change
any verdict until a backtest supports it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import bnn, jaimini
from core.constants import SIGN_LORDS, SIGNS

DAYS_PER_YEAR = 365.25
VISHAMA = {0, 1, 2, 6, 7, 8}
PAIRS = {7: ("Mars", "Ketu"), 10: ("Saturn", "Rahu")}


MOVABLE, FIXED, DUAL = {0, 3, 6, 9}, {1, 4, 7, 10}, {2, 5, 8, 11}
HOUSE_THEME = jaimini.HOUSE_THEME


def rashi_aspects(sign: int) -> set[int]:
    """Signs that a sign aspects (Jaimini): movable -> fixed, fixed -> movable, except the adjacent one; dual -> dual."""
    if sign in MOVABLE:
        return FIXED - {(sign + 1) % 12}
    if sign in FIXED:
        return MOVABLE - {(sign - 1) % 12}
    return DUAL - {sign}


def _jd_to_utc(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def lord_for_count(sign: int, signs: dict, degs: dict) -> str:
    """The planet whose sign the dasha years are counted to."""
    pair = PAIRS.get(sign)
    if not pair:
        return SIGN_LORDS[sign]
    a, b = pair
    inside = [p for p in pair if signs[p] == sign]
    if len(inside) == 1:
        return b if inside[0] == a else a
    count = lambda p: sum(1 for q, s in signs.items() if s == signs[p] and q != p)
    if count(a) != count(b):
        return a if count(a) > count(b) else b
    return a if degs[a] >= degs[b] else b


def sign_years(sign: int, signs: dict, degs: dict) -> int:
    lord = lord_for_count(sign, signs, degs)
    target = signs[lord]
    n = (target - sign) % 12 + 1 if sign in VISHAMA else (sign - target) % 12 + 1
    return n - 1 or 12


def mahadasha_order(lagna: int) -> list[int]:
    direct = (lagna + 8) % 12 in VISHAMA  # the 9th sign from the Lagna
    return [(lagna + i) % 12 if direct else (lagna - i) % 12 for i in range(12)]


def sub_order(sign: int) -> list[int]:
    """The twelve sub-period signs, the main sign last."""
    if sign in VISHAMA:
        return [(sign + 1 + i) % 12 for i in range(12)]
    return [(sign - 1 - i) % 12 for i in range(12)]


def chara_dasha(chart: dict, cycles: int = 2) -> list[dict]:
    g = chart["grahas"]
    signs = {p: v["sign_index"] for p, v in g.items()}
    degs = {p: v["degrees_in_sign"] for p, v in g.items()}
    lagna = chart["lagna"]["sign_index"]
    order = mahadasha_order(lagna)
    start, out = _jd_to_utc(chart["meta"]["julian_day"]), []
    for cycle in range(cycles):
        for s in order:
            y = sign_years(s, signs, degs)
            years = y if cycle == 0 else 12 - y
            if years <= 0:
                continue
            end = start + timedelta(days=years * DAYS_PER_YEAR)
            subs, t = [], start
            for si in sub_order(s):
                e = t + timedelta(days=years * DAYS_PER_YEAR / 12)
                subs.append({"sign": SIGNS[si], "sign_index": si, "start": t.isoformat(), "end": e.isoformat()})
                t = e
            out.append({"sign": SIGNS[s], "sign_index": s, "house": (s - lagna) % 12 + 1, "years": years,
                        "start": start.isoformat(), "end": end.isoformat(), "sub": subs,
                        "planets": [p for p, x in signs.items() if x == s]})
            start = end
    return out


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


KARAKA_FOCUS = {
    "AK": "a time to find your own direction and take charge of your path",
    "AmK": "work, responsibility and advisers are in focus — a good time to build your career",
    "BK": "siblings, mentors and courage come forward",
    "MK": "home, mother and property come forward",
    "PiK": "your father and guidance from elders come forward",
    "PK": "children, studies and creative work come forward",
    "GK": "rivals and obstacles surface — handle them with patience and good advice",
    "DK": "relationships and partnerships come forward",
}


def interpret(chart: dict, sign: int, role: str = "period") -> dict:
    """What a Chara Dasha sign means for this person, treating the sign as a temporary Lagna (Jaimini layers):
    who sits in it, who aspects it (Rashi drishti), which karakas and special points it touches."""
    g, L = chart["grahas"], chart["lagna"]["sign_index"]
    j = chart.get("jaimini") or jaimini.analyse(chart)
    signs = {p: v["sign_index"] for p, v in g.items()}
    karaka = {k["planet"]: k["short"] for k in j["karakas"]}
    name = SIGNS[sign]
    house = (sign - L) % 12 + 1
    tag = lambda p: f"{p}" + (f" (your {karaka[p]})" if p in karaka else "")
    inside = [p for p, s in signs.items() if s == sign]
    seen = [p for p, s in signs.items() if s != sign and sign in rashi_aspects(s)]
    pts = []
    if inside:
        pts.append(f"{', '.join(tag(p) for p in inside)} {'sit' if len(inside) > 1 else 'sits'} in {name}, so "
                   + "; ".join(f"{p} brings {bnn.ADDS[p]}" for p in inside) + " into this period.")
    else:
        pts.append(f"No planet sits in {name}, so this period is shaped by the planets that look at it and by its lord.")
    if seen:
        pts.append(f"By Jaimini's sign aspects, {', '.join(tag(p) for p in seen)} also {'look' if len(seen) > 1 else 'looks'} at {name}.")
    ks = list(dict.fromkeys(karaka[p] for p in inside + seen if p in karaka))
    focus = [KARAKA_FOCUS[k] for k in ks if k in KARAKA_FOCUS]
    if "AK" in ks and "AmK" in ks:
        pts.append("Your soul planet and your career planet are both linked to this sign — one of Jaimini's classic marks "
                   "of rising status and recognition.")
    marks = []
    names = {"AL": j["arudha_lagna"]["sign"], "UL": j["upapada"]["sign"]}
    if name == names["AL"]:
        marks.append("this is your Arudha Lagna sign: your public image and status are in the spotlight")
    if name == names["UL"]:
        marks.append("this is your Upapada sign: marriage and commitment themes come forward")
    if j["karakamsa"] and name == j["karakamsa"]["sign"]:
        marks.append("this is your Karakamsa sign: your deeper life purpose is active")
    al_i = SIGNS.index(names["AL"])
    if sign == (al_i + 10) % 12:
        marks.append("this sign is 11th from your Arudha Lagna, a sign of gains and a growing network")
    if sign == (al_i + 11) % 12:
        marks.append("this sign is 12th from your Arudha Lagna, so watch spending and keep a cushion")
    pts += [m[0].upper() + m[1:] + "." for m in marks]
    pts += [f"{f[0].upper() + f[1:]}." for f in focus if not f.startswith("work, responsibility") or "AK" not in ks or "AmK" not in ks]
    if house in (6, 8, 12) and not focus:
        pts.append("It sits in a house of service, research and inner work: a time to go steady and look after your health.")
    head = (f"{name} acts as a temporary Lagna for this {role}: {HOUSE_THEME[house]} come to the front "
            f"(your {_ord(house)} house).")
    return {"sign": name, "house": house, "headline": head, "points": pts}


def summary(chart: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    periods = chara_dasha(chart)
    iso = now.isoformat()
    cur = next((p for p in periods if p["start"] <= iso < p["end"]), None)
    sub = cur and next((s for s in cur["sub"] if s["start"] <= iso < s["end"]), None)
    nxt = cur and next((p for p in periods if p["start"] >= cur["end"]), None)
    i = periods.index(cur) if cur else 0
    slim = lambda p: {k: v for k, v in p.items() if k != "sub"}
    read = {"now": cur and interpret(chart, cur["sign_index"], "main period"),
            "sub": sub and interpret(chart, sub["sign_index"], "sub-period"),
            "next": nxt and interpret(chart, nxt["sign_index"], "main period")}
    return {"current": cur and slim(cur), "sub": sub, "next": nxt and slim(nxt), "reading": read,
            "timeline": [slim(p) for p in periods[max(0, i - 1): i + 6]],
            "current_subs": cur["sub"] if cur else [],
            "note": "Sign-based timing (K.N. Rao's counting): each period treats its sign as a temporary Lagna."}
