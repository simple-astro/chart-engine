"""Married life: for a couple who are already married, how they rate six areas of their marriage, how that compares
with the match (each koota is one area), what helps, and the days to talk and the days to be patient.

Ratings change the guidance, never the chart: the habits shown are for the areas that are weak in the chart or in
the person's own experience. Ratings are private to the person who gives them. Habit wording is curated content
(remedy library, kind "couple"): only approved habits are served when the tester gate is on.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from core import kp_predict as K
from core.ephemeris import julian_day, sidereal_longitude

# area key, what we ask, the koota it compares with
AREAS = [("gana", "Similar temperament", "Gana"), ("bhakoot", "Emotional closeness", "Bhakoot"),
         ("maitri", "Understanding each other", "Graha Maitri"), ("yoni", "Physical closeness", "Yoni"),
         ("vashya", "Who leads, who adjusts", "Vashya"), ("nadi", "Health and family", "Nadi")]
TRENDS = {"hard_then_better": "Hard at first, then better", "steady": "Steady", "harder_lately": "Harder lately",
          "ups_and_downs": "Ups and downs"}
BAD_TARA = (3, 5, 7)            # Vipat, Pratyak, Naidhana (counted from each person's birth star)
TOUGH_FROM_MOON = (6, 8, 12)
PLAN_DAYS = 43
STEADY = {"strong": "Supportive", "favourable": "Supportive", "mixed": "Mixed"}  # anything else: Demanding


def level(got: float, mx: float) -> str:
    return "high" if got / mx >= 0.75 else "mid" if got / mx >= 0.4 else "low"


def felt(v: int | None) -> str | None:
    return None if not v else "high" if v >= 4 else "mid" if v == 3 else "low"


def compare(match: dict, ratings: dict) -> dict:
    """Each area: what the person said, what the koota says, and whether they agree."""
    k = {x["name"]: x for x in match["kootas"]}
    rows = []
    for key, label, koota in AREAS:
        x = k[koota]
        rows.append({"area": key, "label": label, "koota": koota, "got": x["got"], "max": x["max"],
                     "chart": level(x["got"], x["max"]), "you": felt(ratings.get(key)), "rating": ratings.get(key)})
    rated = [r for r in rows if r["you"]]
    agree = [r for r in rated if r["you"] == r["chart"]]
    hard = [r["label"].lower() for r in agree if r["chart"] == "low"]
    text = (f"Your experience matches your charts in {len(agree)} of {len(rated)} areas"
            + (f", including the hardest: {' and '.join(hard)}." if hard else ".")) if rated else ""
    return {"rows": rows, "agree": len(agree), "rated": len(rated), "text": text}


def habits(rows: list[dict], items: list[dict]) -> list[dict]:
    """Habits for the areas that need care (low in the chart or rated hard), then one for every couple."""
    weak = [r["area"] for r in sorted(rows, key=lambda r: (r["you"] != "low", r["chart"] != "low", r["got"] / r["max"]))
            if r["chart"] == "low" or r["you"] == "low"]
    out = []
    for area in weak[:3]:
        r = next(x for x in rows if x["area"] == area)
        for it in [i for i in items if i["area"] == area][:2]:
            out.append({**_habit(it), "area_label": r["label"], "koota": f"{r['koota']} {_n(r['got'])}/{r['max']}"})
    out += [{**_habit(i), "area_label": "Every couple", "koota": None} for i in items if i["area"] == "general"][:1]
    return out


def _habit(i: dict) -> dict:
    return {"slug": i["slug"], "title": i["title"], "text": i["text"], "why": i.get("why"), "who": i["who"]}


def _n(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


def days(groom: dict, bride: dict, start: date, n: int, tz: str, names: tuple[str, str]) -> list[dict]:
    """Talk days and patience days for the couple, at local noon.

    Patience day (Chandrashtama): the Moon in the 8th sign from either person's Moon. Talk day: neither has a
    difficult Tara (Vipat, Pratyak, Naidhana) and the Moon is not 6th, 8th or 12th from either Moon."""
    ay = groom["meta"].get("ayanamsha", "krishnamurti")
    people = [(names[0], groom["grahas"]["Moon"]), (names[1], bride["grahas"]["Moon"])]
    out = []
    for i in range(n):
        d = start + timedelta(days=i)
        noon = datetime(d.year, d.month, d.day, 12, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)
        lon, _ = sidereal_longitude(julian_day(noon), swe.MOON, ay)
        s, nk = int(lon // 30) % 12, int(lon // (360 / 27)) % 27
        from_moon = [(s - m["sign_index"]) % 12 + 1 for _, m in people]
        tara = [(nk - m["nakshatra_index"]) % 9 + 1 for _, m in people]
        patience = [nm for (nm, _), h in zip(people, from_moon) if h == 8]
        talk = not patience and all(t not in BAD_TARA for t in tara) and all(h not in TOUGH_FROM_MOON for h in from_moon)
        out.append({"date": d.isoformat(), "kind": "patience" if patience else "talk" if talk else None,
                    "who": patience})
    return out


def early_years(charts: list[tuple[str, dict]], wedding: date | None, years: int = 5) -> list[dict]:
    """Each partner's Antardasha periods in the first years of the marriage, read for marriage (gentle labels)."""
    if not wedding:
        return []
    out = []
    for name, chart in charts:
        seen: dict[str, dict] = {}
        for p in K.verdict_spans(chart, "marriage", wedding, wedding + timedelta(days=round(years * 365.25))):
            key = f"{p['maha']}–{p['antar']}"
            s = seen.setdefault(key, {"who": name, "period": key, "start": p["starts"], "end": p["ends"], "v": []})
            s["end"] = max(s["end"], p["ends"])
            s["v"].append(p["verdict"])
        for s in seen.values():
            v = s.pop("v")
            label = max(set(map(lambda x: STEADY.get(x, "Demanding"), v)), key=lambda x: [STEADY.get(y, "Demanding") for y in v].count(x))
            out.append({**s, "label": label, "start": max(s["start"], wedding).isoformat(), "end": s["end"].isoformat()})
    return sorted(out, key=lambda x: (x["start"], x["who"]))


def plan_day(plan_start: str | None, today: date) -> int | None:
    if not plan_start:
        return None
    n = (today - date.fromisoformat(plan_start)).days + 1
    return n if 1 <= n <= PLAN_DAYS else None
