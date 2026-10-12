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

from core.constants import SIGN_LORDS, SIGNS

DAYS_PER_YEAR = 365.25
VISHAMA = {0, 1, 2, 6, 7, 8}
PAIRS = {7: ("Mars", "Ketu"), 10: ("Saturn", "Rahu")}


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


def summary(chart: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    periods = chara_dasha(chart)
    iso = now.isoformat()
    cur = next((p for p in periods if p["start"] <= iso < p["end"]), None)
    sub = cur and next((s for s in cur["sub"] if s["start"] <= iso < s["end"]), None)
    nxt = cur and next((p for p in periods if p["start"] >= cur["end"]), None)
    i = periods.index(cur) if cur else 0
    slim = lambda p: {k: v for k, v in p.items() if k != "sub"}
    return {"current": cur and slim(cur), "sub": sub, "next": nxt and slim(nxt),
            "timeline": [slim(p) for p in periods[max(0, i - 1): i + 6]],
            "current_subs": cur["sub"] if cur else [],
            "note": "Sign-based timing (K.N. Rao's counting): each period treats its sign as a temporary Lagna."}
