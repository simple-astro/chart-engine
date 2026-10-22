"""Connections between two birth charts for match making: which planet of one partner touches which house or planet
of the other, coloured supportive (green), mixed (yellow) or needs care (red). Drawn as arrows between the charts.

Read by sign from the chart_view() data (core/matchmaking.py), the same way for D1 and D9:
- Moon to Moon by the sign distance: 1/1, 1/7, 3/11, 4/10 support; 2/12 and 5/9 are mixed (5/9 is a mild Bhakoot in
  the common North-Indian table); 6/8 needs care, as does the same Nadi.
- Venus in the other's Lagna or 7th: attraction and commitment (green).
- Jupiter on or aspecting (5th, 7th, 9th) the other's Lagna, 7th or Moon: protection (green).
- The Lagna lord in the other's Lagna or 7th, and the 7th lord in the other's Lagna or Moon sign (green).
- Venus and Mars across the charts: same sign, trine or 3/11 is chemistry (green); opposite is attraction with
  friction (yellow).
- Saturn on the other's Moon, Venus, Lagna or 7th: commitment with weight (yellow).
- Rahu or Ketu on the other's Moon or Venus: a strong, unsettled pull (yellow).
- Mars on the other's Moon, Venus or 7th: heat and quarrels (red).
Each link names both ends (who, planet or house, and the house it sits in within that person's own chart) so the app
can draw it, and says what it rests on. Tendencies, never verdicts.
"""
from __future__ import annotations

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
         "Aquarius", "Pisces"]
SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn",
             "Jupiter"]
ORDER = {"green": 0, "yellow": 1, "red": 2}


def _dist(a: int, b: int) -> int:
    """Sign distance counted from a to b, 1..12."""
    return (b - a) % 12 + 1


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _house(v: dict, sign: int) -> int:
    return _dist(v["lagna"], sign)


def links(g: dict, b: dict, names: tuple[str, str], nadi_same: bool = False) -> list[dict]:
    """Every connection between the groom's and bride's charts (chart_view()["d1"] or ["d9"]), strongest first
    within green, then yellow, then red."""
    people = {"groom": (g, names[0]), "bride": (b, names[1])}
    out: list[dict] = []
    seen: set[tuple] = set()

    def end(who: str, planet: str | None = None, house: int | None = None) -> dict:
        v, name = people[who]
        if planet:
            return {"who": who, "name": name, "planet": planet, "house": _house(v, v["planets"][planet]["sign"])}
        return {"who": who, "name": name, "planet": None, "house": house}

    def add(kind: str, weight: float, a: dict, z: dict, title: str, text: str, why: str) -> None:
        key = (a["who"], a["planet"], a["house"], z["who"], z["planet"], z["house"])
        if key in seen:
            return
        seen.add(key)
        out.append({"kind": kind, "weight": weight, "from": a, "to": z, "title": title, "text": text, "why": why})

    # Moon to Moon, once for the pair
    gm, bm = g["planets"]["Moon"]["sign"], b["planets"]["Moon"]["sign"]
    d1, d2 = _dist(gm, bm), _dist(bm, gm)
    pair = "1/1" if d1 == 1 else "1/7" if d1 == 7 else f"{min(d1, d2)}/{max(d1, d2)}"
    if nadi_same:
        kind, text = "red", "Same Nadi: traditionally a concern for health and children; see the Nadi dosha notes."
    elif pair in ("6/8",):
        kind, text = "red", "Moods can pull in different directions; patience and space help."
    elif pair in ("2/12", "5/9"):
        kind, text = "yellow", ("Your feelings run in tune, though many traditions count 5/9 as a mild Bhakoot dosha."
                                if pair == "5/9" else "Close but different rhythms; small kindnesses keep you in step.")
    else:
        kind, text = "green", "Your minds and moods meet easily."
    add(kind, 3, end("groom", "Moon"), end("bride", "Moon"), "Moons in the same sign" if pair == "1/1" else f"Moons {pair} apart", text,
        f"{names[0]}'s Moon in {SIGNS[gm]}, {names[1]}'s in {SIGNS[bm]}.")

    for x, y in (("groom", "bride"), ("bride", "groom")):
        X, xn = people[x]
        Y, yn = people[y]
        P = X["planets"]
        y_lag, y_7, y_moon, y_ven = Y["lagna"], (Y["lagna"] + 6) % 12, Y["planets"]["Moon"]["sign"], Y["planets"]["Venus"]["sign"]

        def lands(planet: str) -> int:
            return P[planet]["sign"]

        # Venus in the other's Lagna or 7th
        for tgt, h, word in ((y_7, 7, "7th house"), (y_lag, 1, "Lagna")):
            if lands("Venus") == tgt:
                add("green", 2.5, end(x, "Venus"), end(y, house=h), f"{xn}'s Venus in {yn}'s {word}",
                    "Natural attraction and a wish to commit.", f"{xn}'s Venus is in {SIGNS[tgt]}, {yn}'s {word}.")
                break
        # Jupiter on or aspecting the other's Lagna, 7th or Moon
        for tgt, h, planet, word in ((y_lag, 1, None, "Lagna"), (y_7, 7, None, "7th house"), (y_moon, None, "Moon", "Moon")):
            d = _dist(lands("Jupiter"), tgt)
            if d in (1, 5, 7, 9):
                how = "sits on" if d == 1 else "aspects"
                add("green", 2.4 if h == 1 else 2.2, end(x, "Jupiter"), end(y, planet, h),
                    f"{xn}'s Jupiter blesses {yn}'s {word}", "Protection, wisdom and good counsel in the marriage.",
                    f"{xn}'s Jupiter in {SIGNS[lands('Jupiter')]} {how} {yn}'s {word} ({SIGNS[tgt]}).")
                break
        # Lagna lord and 7th lord
        L1, L7 = SIGN_LORD[X["lagna"]], SIGN_LORD[(X["lagna"] + 6) % 12]
        for tgt, h, word in ((y_lag, 1, "Lagna"), (y_7, 7, "7th house")):
            if lands(L1) == tgt:
                add("green", 2.3, end(x, L1), end(y, house=h), f"{xn}'s Lagna lord in {yn}'s {word}",
                    "A strong natural bond: one feels at home in the other's life.",
                    f"{L1} rules {xn}'s Lagna and sits in {yn}'s {word} ({SIGNS[tgt]}).")
                break
        for tgt, h, planet, word in ((y_lag, 1, None, "Lagna"), (y_moon, None, "Moon", "Moon sign")):
            if lands(L7) == tgt:
                add("green", 2.1, end(x, L7), end(y, planet, h), f"{xn}'s 7th lord on {yn}'s {word}",
                    "The partner one looks for is found in the other.",
                    f"{L7} rules {xn}'s 7th house and sits in {yn}'s {word} ({SIGNS[tgt]}).")
                break
        # Venus and Mars across the charts (once per direction: x's Mars with y's Venus)
        d = _dist(lands("Mars"), y_ven)
        if d in (1, 5, 9, 3, 11):
            add("green", 1.8, end(x, "Mars"), end(y, "Venus"), f"{xn}'s Mars and {yn}'s Venus",
                "Easy chemistry: attraction comes and stays friendly.",
                f"{xn}'s Mars in {SIGNS[lands('Mars')]} and {yn}'s Venus in {SIGNS[y_ven]} ({'same sign' if d == 1 else f'{min(d, 14 - d)}/{max(d, 14 - d)}'}).")
        elif d == 7:
            add("yellow", 1.8, end(x, "Mars"), end(y, "Venus"), f"{xn}'s Mars opposite {yn}'s Venus",
                "Strong attraction with some friction.", f"{xn}'s Mars in {SIGNS[lands('Mars')]}, {yn}'s Venus in {SIGNS[y_ven]}.")
        # Saturn on the other's Moon, Venus, Lagna or 7th
        for tgt, h, planet, word in ((y_moon, None, "Moon", "Moon"), (y_ven, None, "Venus", "Venus"), (y_lag, 1, None, "Lagna"), (y_7, 7, None, "7th house")):
            if lands("Saturn") == tgt:
                add("yellow", 2, end(x, "Saturn"), end(y, planet, h), f"{xn}'s Saturn on {yn}'s {word}",
                    "Steady and loyal, though it can feel serious or cool; warm gestures matter.",
                    f"{xn}'s Saturn sits in {SIGNS[tgt]}, with {yn}'s {word}.")
                break
        # Rahu or Ketu on the other's Moon or Venus
        for node in ("Rahu", "Ketu"):
            hit = [(p, w) for p, w in (("Moon", "Moon"), ("Venus", "Venus")) if lands(node) == Y["planets"][p]["sign"]]
            if hit:
                both = " and ".join(w for _, w in hit)
                add("yellow", 2.2 if node == "Rahu" else 1.6, end(x, node), end(y, hit[0][0]), f"{xn}'s {node} on {yn}'s {both}",
                    "A strong, almost fated pull; feelings can swing, so keep talking openly." if node == "Rahu"
                    else "A deep but detached tie; make time to feel close.",
                    f"{xn}'s {node} in {SIGNS[lands(node)]} sits on {yn}'s {both}.")
        # Mars on the other's Moon, Venus or 7th
        for tgt, h, planet, word in ((y_7, 7, None, "7th house"), (y_moon, None, "Moon", "Moon"), (y_ven, None, "Venus", "Venus")):
            if lands("Mars") == tgt:
                add("red", 2.2 if h == 7 else 2, end(x, "Mars"), end(y, planet, h), f"{xn}'s Mars on {yn}'s {word}",
                    "Heat between you: quick tempers can flare. Pause before reacting.",
                    f"{xn}'s Mars sits in {SIGNS[tgt]}, {yn}'s {word}.")
                break

    out.sort(key=lambda l: (ORDER[l["kind"]], -l["weight"]))
    for i, l in enumerate(out):
        l["n"] = i + 1
    return out


def summary(ls: list[dict]) -> dict:
    """Counts and one sentence: the strongest supportive link, and what to watch."""
    c = {k: sum(1 for l in ls if l["kind"] == k) for k in ORDER}
    best = next((l for l in ls if l["kind"] == "green"), None)
    watch = [l for l in ls if l["kind"] == "red"] + [l for l in ls if l["kind"] == "yellow"]
    s = f"Strongest link: {best['title']}." if best else "Few direct links between the charts."
    if watch:
        s += " Watch: " + "; ".join(w["title"] for w in watch[:2]) + "."
    return {"counts": c, "text": s}
