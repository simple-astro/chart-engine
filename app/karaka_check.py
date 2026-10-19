"""Past events checked by natural karakas (the Parashari way), beside the KP check in life_events.

DRAFT rules, waiting for the mentor's review (PENDING_IDEAS.md idea 15):
- Period: the Maha or Antar lord IS the event's natural karaka, the lord of its house, or a planet in that house;
  the Pratyantar lord may also count by sitting with the karaka or house lord, or aspecting the house.
- Trigger (double transit): on that day Jupiter and Saturn each sit in or aspect (graha drishti) the house or the
  sign of its lord, counted from the Lagna or from the Moon.
- Fits = period and trigger; partly = one of them; doesn't fit = neither.
Whole-sign houses from the chart's own Lagna and Moon; transits in the chart's own ayanamsha.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone

from core import constants as C
from core.transits import transit_positions

DRAFT_NOTE = "Karaka rules are a first draft waiting for our mentor's review."
# life matter (life_events topic) -> (natural karakas, houses)
KARAKAS = {
    "marriage": ({"Venus"}, {7}), "love": ({"Venus", "Moon"}, {5}), "divorce": ({"Venus"}, {7}),
    "career": ({"Saturn", "Sun"}, {10}), "job_change": ({"Saturn"}, {10}), "career_loss": ({"Saturn"}, {10, 12}),
    "business": ({"Mercury"}, {7, 10}), "money": ({"Jupiter", "Venus"}, {2, 11}), "windfall": ({"Jupiter", "Rahu"}, {8, 11}),
    "money_loss": ({"Saturn", "Rahu"}, {8, 12}), "property": ({"Mars", "Moon"}, {4}), "property_sale": ({"Mars"}, {4}),
    "vehicle": ({"Venus"}, {4}), "residence": ({"Moon"}, {4}), "foreign": ({"Rahu", "Moon"}, {9, 12}),
    "long_journey": ({"Moon"}, {9, 12}), "pleasure_trip": ({"Venus", "Moon"}, {3, 5}),
    "education": ({"Mercury", "Jupiter"}, {4, 5, 9}), "exams": ({"Mercury", "Jupiter"}, {4, 5, 9}),
    "awards": ({"Sun", "Jupiter"}, {10, 11}), "children": ({"Jupiter"}, {5}), "health": ({"Sun"}, {1}),
    "litigation_win": ({"Mars"}, {6}), "litigation": ({"Mars"}, {6}), "illness": ({"Saturn"}, {6, 8}),
    "accident": ({"Mars"}, {8}), "pilgrimage": ({"Jupiter", "Ketu"}, {9, 12}), "spiritual": ({"Jupiter", "Ketu"}, {9, 12}),
}
ASPECT = {"Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10), "Rahu": (5, 7, 9), "Ketu": (5, 7, 9)}


def _sees(planet: str, frm: int, to: int) -> bool:
    """A planet in sign ``frm`` sits in or casts its full aspect on sign ``to`` (whole signs)."""
    d = (to - frm) % 12 + 1
    return d == 1 or d in ASPECT.get(planet, (7,))


def _lords_at(chart: dict, when: datetime) -> list[tuple[str, str]]:
    iso = when.isoformat()
    out, level = [], chart.get("dasha", [])
    for name in ("maha", "antar", "praty"):
        node = next((d for d in level if d["start"][:19] <= iso[:19] < d["end"][:19]), None)
        if not node:
            break
        out.append((name, node["lord"]))
        level = node.get("children") or []
    return out


def _period(chart: dict, lords: list[tuple[str, str]], kar: set, hs: set) -> list[str]:
    g, L = chart["grahas"], chart["lagna"]["sign_index"]
    house_sign = {h: (L + h - 1) % 12 for h in hs}
    house_lord = {h: C.SIGN_LORDS[s] for h, s in house_sign.items()}
    why = []
    for lvl, p in lords:
        word = {"maha": "Dasha", "antar": "Bhukti", "praty": "Antar"}[lvl]
        if p in kar:
            why.append(f"{word} lord {p} is the karaka")
        elif p in house_lord.values():
            why.append(f"{word} lord {p} rules your {', '.join(f'{h}th' for h, l in house_lord.items() if l == p)}")
        elif g[p]["sign_index"] in house_sign.values():
            why.append(f"{word} lord {p} sits in the house")
        elif lvl == "praty" and (any(g[p]["sign_index"] == g[k]["sign_index"] for k in kar | set(house_lord.values()) if k in g)
                                 or any(_sees(p, g[p]["sign_index"], s) for s in house_sign.values())):
            why.append(f"Antar lord {p} joins the karaka or aspects the house")
    return why


def _trigger(chart: dict, tr: dict, hs: set) -> list[int]:
    g = chart["grahas"]
    out = []
    for base in (chart["lagna"]["sign_index"], g["Moon"]["sign_index"]):
        for h in hs:
            s = (base + h - 1) % 12
            targets = {s, g[C.SIGN_LORDS[s]]["sign_index"]}
            if all(any(_sees(p, tr[p].sign_index, t) for t in targets) for p in ("Jupiter", "Saturn")):
                out.append(h)
    return sorted(set(out))


def _transits(chart: dict, when: datetime) -> dict:
    return transit_positions(when.astimezone(timezone.utc), chart["meta"].get("ayanamsha", "krishnamurti"),
                             chart["meta"].get("node_type", "mean"))


def _days(lo: date, hi: date) -> list[datetime]:
    """The moments to look at: the middle of a single day, else the start, middle and end of the span."""
    mid = lo + (hi - lo) / 2
    picks = [mid] if (hi - lo).days <= 1 else [lo, mid, hi - timedelta(days=1)]
    return [datetime.combine(d, time(12), tzinfo=timezone.utc) for d in picks]


def check(chart: dict, topic: str | None, lo: date, hi: date) -> dict:
    if not topic or topic not in KARAKAS:
        return {"fit": "noted", "why": None}
    kar, hs = KARAKAS[topic]
    best = (0, [], [], None)
    for t in _days(lo, hi):
        lords = _lords_at(chart, t)
        per, trig = _period(chart, lords, kar, hs), _trigger(chart, _transits(chart, t), hs)
        score = bool(per) + bool(trig)
        if score > best[0] or best[3] is None:
            best = (score, per, trig, "–".join(p for _, p in lords))
    score, per, trig, names = best
    fit = "fits" if score == 2 else "partly" if score == 1 else "no"
    karaka = " or ".join(sorted(kar))
    why = (f"{names} period: " + ("; ".join(per[:2]) if per else f"no period lord is {karaka} or linked to the house")
           + (f" · Jupiter and Saturn both touch your {', '.join(f'{h}th' for h in trig)} house" if trig
              else " · no double transit of Jupiter and Saturn on the house"))
    return {"fit": fit, "why": why}


def base_rate(chart: dict, topic: str, birth: date, today: date, samples: int = 120) -> float:
    """How often a random day in adult life would fit (same rules): the chance level."""
    if topic not in KARAKAS:
        return 0.0
    kar, hs = KARAKAS[topic]
    lo = birth + timedelta(days=round(16 * 365.25))
    if lo >= today:
        lo = birth
    rnd = random.Random(f"{chart['meta'].get('julian_day')}{topic}")  # the same answer every time for a chart
    span = (today - lo).days or 1
    fits = 0
    for _ in range(samples):
        t = datetime.combine(lo + timedelta(days=rnd.randrange(span)), time(12), tzinfo=timezone.utc)
        fits += bool(_period(chart, _lords_at(chart, t), kar, hs)) and bool(_trigger(chart, _transits(chart, t), hs))
    return fits / samples
