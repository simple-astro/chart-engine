"""Bhrigu Nandi Nadi (BNN): planets read as living karakas, joined through their signs — for readings only.

- Element trines: planets in the 1st, 5th and 9th signs from each other (Fire, Earth, Air, Water) act as if joined.
  Within a group the planet at the lower degree in its sign gives its results earlier in life.
- From a karaka's sign, the 2nd sign shows what comes next (where its energy flows) and the 12th what lies behind
  it (past karma, background support); the 7th sign is its partner or opposite.
- An exchange of signs (parivartana) with the karaka binds the two planets' themes together.
- Fixed karakas: Jupiter = the self in a man's chart (and husband in a woman's), Venus = the self in a woman's chart
  (and wife / spouse in a man's) and wealth, Saturn = career and karma, Mercury = education and intellect,
  Mars = energy, land and siblings, Moon = mind and mother, Sun = father and authority.
The app does not ask for gender, so both readings of Jupiter and Venus are named. No timing comes from this view:
BNN transit timing would need a backtest first.
"""
from __future__ import annotations

from core.constants import SIGN_LORDS, SIGNS

ELEMENTS = [("Fire", (0, 4, 8)), ("Earth", (1, 5, 9)), ("Air", (2, 6, 10)), ("Water", (3, 7, 11))]
KARAKAS = {
    "Jupiter": "you (in a man's chart) or the husband (in a woman's chart); also children and teachers",
    "Venus": "you (in a woman's chart) or the wife (in a man's chart); also wealth and comforts",
    "Saturn": "career, work and karma",
    "Mercury": "education, intellect and trade",
    "Mars": "energy, land, property and siblings",
    "Moon": "mind and mother",
    "Sun": "father, authority and the soul",
}
SHORT = {"Jupiter": "self / husband", "Venus": "self / wife, wealth", "Saturn": "career", "Mercury": "education",
         "Mars": "energy, property", "Moon": "mind, mother", "Sun": "father, authority"}
ADDS = {"Sun": "authority and recognition", "Moon": "feeling, public contact and change",
        "Mars": "drive, technical skill and property", "Mercury": "intellect, trade and communication",
        "Jupiter": "wisdom, guidance and growth", "Venus": "comfort, art, money and relationships",
        "Saturn": "hard work, structure and service", "Rahu": "ambition, foreign links and the unusual",
        "Ketu": "detachment, research and inner depth"}
ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def _list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _element(sign: int) -> str:
    return next(name for name, signs in ELEMENTS if sign in signs)


def analyse(chart: dict) -> dict:
    g = chart["grahas"]
    sign = {p: g[p]["sign_index"] for p in ORDER}
    deg = {p: g[p]["degrees_in_sign"] for p in ORDER}
    trines = []
    for name, signs in ELEMENTS:
        ps = sorted((p for p in ORDER if sign[p] in signs), key=lambda p: deg[p])
        trines.append({"element": name, "signs": [SIGNS[s] for s in signs],
                       "planets": [{"planet": p, "sign": SIGNS[sign[p]], "degree": round(deg[p], 2)} for p in ps]})
    at = lambda s: [p for p in ORDER if sign[p] == s % 12]
    circuits = []
    for k, role in KARAKAS.items():
        s = sign[k]
        joined = [p for p in ORDER if p != k and sign[p] in dict(ELEMENTS)[_element(s)]]
        joined.sort(key=lambda p: deg[p])
        ahead, behind, opposite = at(s + 1), at(s + 11), at(s + 6)
        lord = SIGN_LORDS[s]
        exchange = lord if lord != k and SIGN_LORDS[sign[lord]] == k else None
        text = []
        if joined:
            same = [p for p in joined if sign[p] == s]
            trine = [p for p in joined if sign[p] != s]
            first = [p for p in joined if deg[p] < deg[k]]
            parts = []
            if same:
                parts.append(f"in the same sign by {_list([f'{p} ({ADDS[p]})' for p in same])}")
            if trine:
                parts.append(f"through the {_element(s).lower()} trine by {_list([f'{p} ({ADDS[p]})' for p in trine])}")
            text.append(f"{k} ({SHORT[k]}) is joined " + "; and ".join(parts) + ".")
            if first:
                text.append(f"{_list(first)} {'have' if len(first) > 1 else 'has'} a lower degree than {k}, "
                            f"so {'their' if len(first) > 1 else 'its'} themes show up first in life.")
        else:
            text.append(f"{k} ({SHORT[k]}) stands alone in its trine: it works through its own sign, {SIGNS[s]}.")
        if ahead:
            text.append(f"Ahead of it (2nd sign): {_list(ahead)} — where this area is heading.")
        if behind:
            text.append(f"Behind it (12th sign): {_list(behind)} — the background that supports it.")
        if opposite:
            text.append(f"Opposite it (7th sign): {_list(opposite)} — a partner or counterweight.")
        if exchange:
            text.append(f"{k} and {exchange} exchange signs: their themes are bound together.")
        circuits.append({"karaka": k, "role": role, "sign": SIGNS[s], "joined": joined, "ahead": ahead,
                         "behind": behind, "opposite": opposite, "exchange": exchange, "text": text})
    return {"trines": trines, "circuits": circuits}
