"""Bhrigu Nandi Nadi (BNN): planets read as living karakas, joined through their signs — for readings only.

- Element trines: planets in the 1st, 5th and 9th signs from each other (Fire, Earth, Air, Water) act as if joined.
  Within a group the planet at the lower degree in its sign gives its results earlier in life.
- From a karaka's sign, the 2nd sign shows what comes next (where its energy flows) and the 12th what lies behind
  it (past karma, background support); the 7th sign is its partner or opposite.
- An exchange of signs (parivartana) with the karaka binds the two planets' themes together.
- A retrograde planet also gives the results of the sign before its own (BNN rule), so it is counted in both:
  in that sign's trine and in the next / behind / opposite links from it. Rahu and Ketu always move backwards and
  are read from their own sign only.
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
    retro = {p: bool(g[p].get("retrograde")) and p not in ("Rahu", "Ketu") for p in ORDER}
    # Where each planet acts: its own sign, and the sign before it when retrograde.
    pos = {p: [sign[p]] + ([(sign[p] - 1) % 12] if retro[p] else []) for p in ORDER}
    trines = []
    for name, signs in ELEMENTS:
        members = sorted(((p, s) for p in ORDER for s in pos[p] if s in signs), key=lambda x: deg[x[0]])
        trines.append({"element": name, "signs": [SIGNS[s] for s in signs],
                       "planets": [{"planet": p, "sign": SIGNS[s], "degree": round(deg[p], 2), "retro": retro[p],
                                    "also": s != sign[p]} for p, s in members]})

    def near(ks: list[int], offset: int, among: list[str], own_only: bool) -> list[str]:
        return [p for p in among if any((x - k0) % 12 == offset for k0 in ks for x in ([sign[p]] if own_only else pos[p]))]

    circuits = []
    trine_of = lambda ss: {x for t in ss for x in dict(ELEMENTS)[_element(t)]}
    for k, role in KARAKAS.items():
        s = sign[k]
        others = [p for p in ORDER if p != k]
        extra = pos[k][1:]  # the sign before, when the karaka is retrograde
        # From the karaka's own sign (other planets count at both their places when retrograde)...
        joined = sorted((p for p in others if set(pos[p]) & trine_of([s])), key=lambda p: deg[p])
        ahead, behind, opposite = (near([s], o, others, False) for o in (1, 11, 6))
        # ...and from the sign before, for a retrograde karaka: only links not already there.
        x_joined = sorted((p for p in others if extra and set(pos[p]) & trine_of(extra) and p not in joined), key=lambda p: deg[p])
        mine = {1: ahead, 11: behind, 6: opposite}
        x_rel = {o: [p for p in near(extra, o, others, False) if p not in joined and p not in x_joined and p not in mine[o]]
                 for o in (1, 11, 6)}
        # A planet counted at its retrograde (previous-sign) place is named as such.
        at_own = lambda p, test: test(sign[p])
        nm = lambda p, test: f"retrograde {p}" if retro[p] and not at_own(p, test) else p
        in_trine = lambda x: x in trine_of([s])
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
                parts.append(f"through the {_element(s).lower()} trine by "
                             f"{_list([f'{nm(p, in_trine)} ({ADDS[p]})' for p in trine])}")
            text.append(f"{k} ({SHORT[k]}) is joined " + "; and ".join(parts) + ".")
            if first:
                text.append(f"{_list(first)} {'have' if len(first) > 1 else 'has'} a lower degree than {k}, "
                            f"so {'their' if len(first) > 1 else 'its'} themes show up first in life.")
        else:
            text.append(f"{k} ({SHORT[k]}) stands alone in its trine: it works through its own sign, {SIGNS[s]}.")
        off = lambda o: (lambda x: (x - s) % 12 == o)
        if ahead:
            text.append(f"What comes next: {_list([nm(p, off(1)) for p in ahead])} {'are' if len(ahead) > 1 else 'is'} in the next "
                        f"sign, so for {AREA[k]} the direction of travel is toward "
                        + "; and ".join(f"{NEXT[p]}{f' (via {p})' if len(ahead) > 1 else ''}" for p in ahead) + ".")
        if behind:
            text.append(f"What stands behind it: {_list([nm(p, off(11)) for p in behind])} {'are' if len(behind) > 1 else 'is'} in "
                        f"the sign just before, so for {AREA[k]} the background support is "
                        + "; and ".join(f"{BEHIND[p]}{f' (from {p})' if len(behind) > 1 else ''}" for p in behind) + ".")
        if opposite:
            text.append(f"What balances it: {_list([nm(p, off(6)) for p in opposite])} {'sit' if len(opposite) > 1 else 'sits'} "
                        "opposite, so partners and other people bring " + "; and ".join(f"{ADDS[p]}" for p in opposite)
                        + " into the picture.")
        if retro[k]:
            prev = SIGNS[extra[0]]
            x_same = [p for p in x_joined if extra[0] in pos[p]]
            x_tri = [p for p in x_joined if p not in x_same]
            links = ([f"with {_list(x_same)} in {prev} itself"] if x_same else []) + \
                    ([f"joined through the {_element(extra[0]).lower()} trine by {_list(x_tri)}"] if x_tri else []) + \
                    ([f"{_list(x_rel[1])} next"] if x_rel[1] else []) + ([f"{_list(x_rel[11])} behind"] if x_rel[11] else []) + \
                    ([f"{_list(x_rel[6])} opposite"] if x_rel[6] else [])
            text.append(f"{k} is retrograde, so by the BNN rule it also gives the results of {prev}, the sign before"
                        + (f": from there it is {'; '.join(links)}." if links else " (no other planets link to it from there)."))
        if exchange:
            text.append(f"{k} and {exchange} exchange signs: their themes are bound together.")
        circuits.append({"karaka": k, "role": role, "sign": SIGNS[s], "retro": retro[k],
                         "also_sign": SIGNS[extra[0]] if extra else None, "joined": joined, "ahead": ahead, "behind": behind,
                         "opposite": opposite, "exchange": exchange,
                         "from_also": {"joined": x_joined, "ahead": x_rel[1], "behind": x_rel[11], "opposite": x_rel[6]},
                         "text": text})
    return {"trines": trines, "circuits": circuits}
