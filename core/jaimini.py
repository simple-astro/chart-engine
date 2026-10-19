"""Jaimini (Phase A): Chara Karakas, Karakamsa, Arudha Lagna and Upapada — for readings, not for the verdicts.

- Chara Karakas: the planets ranked by their degrees within their signs. The 7-karaka scheme (Sun to Saturn) gives
  Atma, Amatya, Bhratri, Matri, Putra, Gnati, Dara; the 8-karaka scheme adds Rahu (counted backwards, 30 - degree)
  and Pitri karaka after Matri.
- Karakamsa: the Navamsa sign of the Atmakaraka.
- Arudha of a house: count from the house to its lord, then the same number again from the lord. If that lands in
  the house itself or the 7th from it, take the 10th from there. Arudha Lagna (AL) is the 1st house's arudha;
  Upapada (UL) is the 12th house's.
- Scorpio and Aquarius have two lords (Mars/Ketu, Saturn/Rahu). The stronger is used: the one with more planets
  in its sign; if equal, the one further advanced in its sign.
"""
from __future__ import annotations

from core.constants import SIGN_LORDS, SIGNS

SEVEN = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka", "Putrakaraka", "Gnatikaraka", "Darakaraka"]
EIGHT = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka", "Pitrikaraka", "Putrakaraka", "Gnatikaraka",
         "Darakaraka"]
SHORT = {"Atmakaraka": "AK", "Amatyakaraka": "AmK", "Bhratrikaraka": "BK", "Matrikaraka": "MK", "Pitrikaraka": "PiK",
         "Putrakaraka": "PK", "Gnatikaraka": "GK", "Darakaraka": "DK"}
ROLE = {"Atmakaraka": "your soul's main lesson", "Amatyakaraka": "career and advisers",
        "Bhratrikaraka": "siblings and courage", "Matrikaraka": "mother and home", "Pitrikaraka": "father",
        "Putrakaraka": "children and creativity", "Gnatikaraka": "rivals and obstacles", "Darakaraka": "spouse and partners"}
SOUL = {"Sun": "learning to lead without ego, and to respect authority",
        "Moon": "caring for others while keeping your own mind steady",
        "Mars": "turning courage and energy into discipline, not anger",
        "Mercury": "using your mind and words wisely; learning, judging well",
        "Jupiter": "living by wisdom, teaching and faith — and staying humble",
        "Venus": "love, beauty and comfort without getting lost in pleasure",
        "Saturn": "patience, duty and steady work; serving others",
        "Rahu": "handling ambition and the unusual without shortcuts"}
CAREER = {"Sun": "government, leadership and administration", "Moon": "public dealing, care, hospitality and food",
          "Mars": "engineering, property, defence, sports or surgery", "Mercury": "business, trade, writing, IT or accounts",
          "Jupiter": "teaching, law, finance, advice or counselling", "Venus": "arts, design, media, fashion or luxury",
          "Saturn": "industry, service, labour, long projects or public works",
          "Rahu": "technology, foreign links and unconventional work"}
SPOUSE = {"Sun": "dignified, proud and principled", "Moon": "caring, emotional and home-loving",
          "Mars": "energetic, direct and protective", "Mercury": "youthful, talkative and clever",
          "Jupiter": "wise, principled and respected", "Venus": "charming, artistic and affectionate",
          "Saturn": "mature, serious and dependable", "Rahu": "unusual, ambitious, perhaps from a different background"}
SIGN_THEME = ["action and initiative", "stability and resources", "ideas and communication", "home and feelings",
              "leadership and recognition", "service and skill", "balance and partnership", "depth and transformation",
              "wisdom and dharma", "duty and achievement", "community and ideals", "spirit and compassion"]
HOUSE_THEME = {1: "your own presence", 2: "wealth and family", 3: "effort and courage", 4: "home and comfort",
               5: "intelligence and creativity", 6: "service and overcoming rivals", 7: "partnerships",
               8: "research and hidden matters", 9: "fortune and dharma", 10: "career and status",
               11: "gains and networks", 12: "foreign lands, giving and spirituality"}
BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def chara_karakas(grahas: dict, scheme: int = 8) -> list[dict]:
    """[{karaka, short, planet, degree, role}] from highest to lowest degree within the sign."""
    deg = {p: grahas[p]["degrees_in_sign"] for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")}
    if scheme == 8:
        deg["Rahu"] = 30.0 - grahas["Rahu"]["degrees_in_sign"]
    names = EIGHT if scheme == 8 else SEVEN
    order = sorted(deg, key=lambda p: -deg[p])
    return [{"karaka": k, "short": SHORT[k], "planet": p, "degree": round(deg[p], 4), "role": ROLE[k]}
            for k, p in zip(names, order)]


def _lord(sign: int, signs: dict) -> str:
    """The sign's lord; for Scorpio and Aquarius, the stronger of its two lords."""
    pair = {7: ("Mars", "Ketu"), 10: ("Saturn", "Rahu")}.get(sign)
    if not pair:
        return SIGN_LORDS[sign]
    count = lambda p: sum(1 for q, s in signs.items() if s == signs[p] and q != p)
    a, b = pair
    if count(a) != count(b):
        return a if count(a) > count(b) else b
    return a if signs.get("_deg", {}).get(a, 0) >= signs.get("_deg", {}).get(b, 0) else b


def arudha(house_sign: int, signs: dict) -> int:
    lord_sign = signs[_lord(house_sign, signs)]
    a = (lord_sign + (lord_sign - house_sign) % 12) % 12
    if a in (house_sign, (house_sign + 6) % 12):
        a = (a + 9) % 12
    return a


ARUDHA = {1: ("AL", "you as a whole — status and image"), 2: ("A2", "your wealth — what people think you have"),
          3: ("A3", "your courage, efforts and siblings"), 4: ("A4", "your home, property and vehicles"),
          5: ("A5", "your intelligence, children and followers"), 6: ("A6", "your rivals, service and health"),
          7: ("A7", "your spouse and business partners (Darapada)"), 8: ("A8", "hidden matters and inheritance"),
          9: ("A9", "your fortune, father and teachers"), 10: ("A10", "your career and reputation at work"),
          11: ("A11", "your gains and network"), 12: ("A12", "your expenses and time abroad")}
MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
NATURE = {"Sun": "proud, official", "Moon": "caring", "Mars": "bold, driven", "Mercury": "clever, business-minded",
          "Jupiter": "wise, respected", "Venus": "charming, artistic", "Saturn": "serious, hard-working",
          "Rahu": "ambitious, unconventional", "Ketu": "detached, spiritual"}


def al_reading(al: int, in_sign) -> list[str]:
    """The classic Jaimini reading of the Arudha Lagna, in plain words (no fear wording)."""
    at = lambda n: in_sign((al + n - 1) % 12)
    ben = lambda ps: [p for p in ps if p in BENEFICS]
    mal = lambda ps: [p for p in ps if p in MALEFICS]
    j = lambda ps: " and ".join(ps)
    out = []
    if at(1):
        out.append(f"{j(at(1))} in your Arudha itself: people see you as {', '.join(NATURE[p] for p in at(1))}.")
    g = ben(at(2) + at(11))
    if g:
        out.append(f"{j(g)} in the 2nd or 11th from your Arudha: money comes in and people see you as prosperous.")
    elif mal(at(11)):
        out.append(f"{j(mal(at(11)))} in the 11th from your Arudha: gains come through hard-fought effort.")
    if ben(at(12)):
        out.append(f"{j(ben(at(12)))} in the 12th from your Arudha: you spend on good causes and people you love.")
    elif mal(at(12)):
        out.append(f"{j(mal(at(12)))} in the 12th from your Arudha: watch for money leaks and needless spending.")
    if mal(at(3) + at(6)):
        out.append(f"{j(mal(at(3) + at(6)))} in the 3rd or 6th from your Arudha: a fighter — you beat competition with drive.")
    elif ben(at(3) + at(6)):
        out.append(f"{j(ben(at(3) + at(6)))} in the 3rd or 6th from your Arudha: you prefer peace to a fight.")
    if at(7):
        out.append(f"{j(at(7))} in the 7th from your Arudha: you attract partners and associates who are "
                   f"{' and '.join(NATURE[p] for p in at(7))}.")
    if not out:
        out.append("No planets sit in the key houses from your Arudha — your image grows steadily through your own work.")
    return out


# Argala (intervention) from the 2nd, 4th and 11th from a sign (the 5th as secondary), each obstructed
# (Virodhargala) by the 12th, 10th, 3rd and 9th from it respectively.
ARGALA = [(2, 12, "primary"), (4, 10, "primary"), (11, 3, "primary"), (5, 9, "secondary")]


def argala(signs: dict, sign: int) -> list[dict]:
    """Argala on ``sign``: who intervenes from each argala house and who obstructs them. An argala holds when it
    has more planets than its obstructing house (simple count; ties count as obstructed). Rahu and Ketu are counted
    like the others; the reverse counting some authors use for Ketu is not applied."""
    at = lambda s: [p for p, x in signs.items() if p != "_deg" and x == s % 12]
    out = []
    for h, v, kind in ARGALA:
        on, against = at(sign + h - 1), at(sign + v - 1)
        if on:
            out.append({"from": h, "kind": kind, "planets": on, "obstructed_from": v, "obstructing": against,
                        "holds": len(on) > len(against)})
    return out


def analyse(chart: dict, scheme: int = 8) -> dict:
    g, L = chart["grahas"], chart["lagna"]["sign_index"]
    signs = {p: v["sign_index"] for p, v in g.items()}
    signs["_deg"] = {p: v["degrees_in_sign"] for p, v in g.items()}
    ks = chara_karakas(g, scheme)
    by = {k["short"]: k["planet"] for k in ks}
    house = lambda s: (s - L) % 12 + 1
    in_sign = lambda s: [p for p, x in signs.items() if p != "_deg" and x == s]

    ak = by["AK"]
    d9 = chart.get("vargas", {}).get("D9", {})
    kk = d9.get(ak, {}).get("sign_index")
    in_kk = [p for p, v in d9.items() if v.get("sign_index") == kk and p != ak] if kk is not None else []

    al = arudha(L, signs)
    ul = arudha((L + 11) % 12, signs)
    second = (ul + 1) % 12
    ul_planets, second_planets = in_sign(ul), in_sign(second)
    arudhas = []
    for h in range(1, 13):
        a = arudha((L + h - 1) % 12, signs)
        arudhas.append({"house": h, "short": ARUDHA[h][0], "shows": ARUDHA[h][1], "sign": SIGNS[a],
                        "in_house": house(a), "planets": in_sign(a)})
    A = {x["short"]: x for x in arudhas}
    a10, a7, a2, a11 = A["A10"], A["A7"], A["A2"], A["A11"]
    mal_2 = [p for p in second_planets if p not in BENEFICS]
    ben_2 = [p for p in second_planets if p in BENEFICS]
    amk, dk = by["AmK"], by["DK"]
    areas = {
        "career": f"Jaimini: your Amatyakaraka {amk} suits {CAREER[amk]}; your career image (A10) sits in your "
                  f"{_ord(a10['in_house'])} house — reputation grows through {HOUSE_THEME[a10['in_house']]}.",
        "love": f"Jaimini: your Darakaraka {dk} points to a partner who is {SPOUSE[dk]}; the Upapada in {SIGNS[ul]} "
                f"gives the marriage a flavour of {SIGN_THEME[ul]}, and A7 in your {_ord(a7['in_house'])} house shows "
                f"partners linked to {HOUSE_THEME[a7['in_house']]}.",
        "money": f"Jaimini: your wealth image (A2) sits in your {_ord(a2['in_house'])} house and your gains (A11) in your "
                 f"{_ord(a11['in_house'])} — money links to {HOUSE_THEME[a2['in_house']]} and {HOUSE_THEME[a11['in_house']]}.",
    }
    plain = {p: x for p, x in signs.items() if p != "_deg"}
    argalas = [{"house": h, "sign": SIGNS[(L + h - 1) % 12], "argala": argala(plain, (L + h - 1) % 12)} for h in range(1, 13)]
    return {
        "scheme": scheme,
        "argala": argalas,
        "arudhas": arudhas,
        "al_reading": al_reading(al, in_sign),
        "areas": areas,
        "purpose": f"Your Atmakaraka is {ak}: your life's main lesson is {SOUL[ak]}."
                   + (f" Your Karakamsa in {SIGNS[kk]} points to a path of {SIGN_THEME[kk]}." if kk is not None else ""),
        "karakas": ks,
        "atmakaraka": {"planet": ak, "lesson": SOUL[ak]},
        "amatyakaraka": {"planet": by["AmK"], "career": CAREER[by["AmK"]]},
        "darakaraka": {"planet": by["DK"], "spouse": SPOUSE[by["DK"]]},
        "karakamsa": None if kk is None else {
            "sign": SIGNS[kk], "theme": SIGN_THEME[kk], "planets": in_kk,
            "note": f"Your Atmakaraka {ak} sits in {SIGNS[kk]} in the Navamsa: a life path of {SIGN_THEME[kk]}"
                    + (f", coloured by {', '.join(in_kk)} there." if in_kk else ".")},
        "arudha_lagna": {"sign": SIGNS[al], "house": house(al), "planets": in_sign(al),
                         "note": f"How the world sees you: through {HOUSE_THEME[house(al)]} ({SIGNS[al]}, your {_ord(house(al))} house)."},
        "upapada": {"sign": SIGNS[ul], "house": house(ul), "planets": ul_planets,
                    "second_from": {"sign": SIGNS[second], "planets": second_planets},
                    "note": (f"Upapada in {SIGNS[ul]} (your {_ord(house(ul))} house): the marriage itself takes on {SIGN_THEME[ul]}."
                             + (f" {' and '.join(ben_2)} in the 2nd from it {'help' if len(ben_2) > 1 else 'helps'} the marriage last." if ben_2 else "")
                             + (f" {' and '.join(mal_2)} in the 2nd from it {'ask' if len(mal_2) > 1 else 'asks'} for patience and care in married life." if mal_2 else ""))},
    }
