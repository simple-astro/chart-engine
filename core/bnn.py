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
# What each karaka's area of life is called in a sentence.
AREA = {"Jupiter": "your path, children and guidance", "Venus": "your relationships, wealth and comforts",
        "Saturn": "your career and work", "Mercury": "your studies and thinking",
        "Mars": "your energy, property and siblings", "Moon": "your mind and home life",
        "Sun": "your standing and your bond with your father"}
# The 2nd sign shows where the energy flows next: what the planet standing there leads toward.
NEXT = {"Sun": "recognition, leadership and standing on your own", "Moon": "feeling, care and contact with people",
        "Mars": "action, drive and taking on challenges", "Mercury": "learning, trade and communication",
        "Jupiter": "wisdom, growth and guidance", "Venus": "comfort, partnership and enjoyment",
        "Saturn": "discipline, responsibility and slow, solid results", "Rahu": "ambition, new experiences and the unusual",
        "Ketu": "research, detachment and letting go of what is finished"}
# The 12th sign shows the background: what the planet standing there has already given.
BEHIND = {"Sun": "confidence and authority from your family and upbringing", "Moon": "emotional support and care from early life",
          "Mars": "energy and courage built through earlier struggles", "Mercury": "learning and skills gathered earlier",
          "Jupiter": "blessings, good advice and protection from the past", "Venus": "comforts and good relationships from the past",
          "Saturn": "hard lessons and discipline from earlier years", "Rahu": "unusual experiences or foreign influence earlier on",
          "Ketu": "inner depth and learning carried over from earlier"}


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
            text.append(f"What comes next: {_list(ahead)} {'are' if len(ahead) > 1 else 'is'} in the next sign, so for {AREA[k]} "
                        "the direction of travel is toward "
                        + "; and ".join(f"{NEXT[p]}{f' (via {p})' if len(ahead) > 1 else ''}" for p in ahead) + ".")
        if behind:
            text.append(f"What stands behind it: {_list(behind)} {'are' if len(behind) > 1 else 'is'} in the sign just before, "
                        f"so for {AREA[k]} the background support is "
                        + "; and ".join(f"{BEHIND[p]}{f' (from {p})' if len(behind) > 1 else ''}" for p in behind) + ".")
        if opposite:
            text.append(f"What balances it: {_list(opposite)} {'sit' if len(opposite) > 1 else 'sits'} opposite, so partners and "
                        f"other people bring " + "; and ".join(f"{ADDS[p]}" for p in opposite) + " into the picture.")
        if exchange:
            text.append(f"{k} and {exchange} exchange signs: their themes are bound together.")
        circuits.append({"karaka": k, "role": role, "sign": SIGNS[s], "joined": joined, "ahead": ahead,
                         "behind": behind, "opposite": opposite, "exchange": exchange, "text": text})
    return {"trines": trines, "circuits": circuits}
