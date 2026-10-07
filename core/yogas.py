"""Graha drishti (aspects), Neecha Bhanga and the main yogas, from whole-sign positions.

Computed here so the chat explains facts instead of inferring them. Houses are counted
whole-sign from the lagna, matching the drawn chart.
"""
from __future__ import annotations

from core.constants import SIGN_LORDS
from core.dignity import EXALT, dignity

SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
# Every graha aspects the 7th sign from itself; Mars, Jupiter and Saturn have special aspects.
# Rahu/Ketu are given 5th/7th/9th, as many Parashari practitioners use.
SPECIAL = {"Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10), "Rahu": (5, 7, 9), "Ketu": (5, 7, 9)}
KENDRA, TRIKONA, DUSTHANA = (1, 4, 7, 10), (1, 5, 9), (6, 8, 12)
MAHAPURUSHA = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya", "Saturn": "Sasa"}


def _from(sign: int, base: int) -> int:
    """House number of ``sign`` counted from ``base`` (1 = same sign)."""
    return (sign - base) % 12 + 1


def aspects(signs: dict[str, int], lagna: int) -> dict:
    out = {}
    for p, s in signs.items():
        hit = [(s + n - 1) % 12 for n in SPECIAL.get(p, (7,))]
        out[p] = {"houses": sorted(_from(x, lagna) for x in hit),
                  "planets": [q for q, t in signs.items() if q != p and t in hit]}
    return out


def _sees(asp: dict, a: str, b: str) -> bool:
    return b in asp[a]["planets"]


def neecha_bhanga(signs: dict[str, int], lagna: int, d9: dict[str, int] | None = None) -> dict:
    """For each debilitated graha, whether classical rules cancel the debilitation, and why."""
    asp, moon = aspects(signs, lagna), signs["Moon"]
    kendra = lambda q: _from(signs[q], lagna) in KENDRA or _from(signs[q], moon) in KENDRA
    where = lambda q: "a kendra from the lagna" if _from(signs[q], lagna) in KENDRA else "a kendra from the Moon"
    out = {}
    for p in SEVEN:
        s = signs[p]
        if dignity(p, s) != "debilitated":
            continue
        lord = SIGN_LORDS[s]                                    # lord of the debilitation sign
        ex_lord = SIGN_LORDS[EXALT[p]]                          # lord of the planet's exaltation sign
        exalted_here = next((q for q in SEVEN if EXALT[q] == s), None)  # planet exalted in this sign
        why = []
        if lord != p and kendra(lord):
            why.append(f"{lord}, lord of the sign it falls in, sits in {where(lord)}")
        if ex_lord != p and ex_lord != lord and kendra(ex_lord):
            why.append(f"{ex_lord}, lord of its exaltation sign, sits in {where(ex_lord)}")
        if exalted_here and exalted_here != p and kendra(exalted_here):
            why.append(f"{exalted_here}, which is exalted in this sign, sits in {where(exalted_here)}")
        if lord != p and (signs[lord] == s or _sees(asp, lord, p)):
            why.append(f"{lord}, lord of the sign, is {'with' if signs[lord] == s else 'aspecting'} it")
        if d9 and d9.get(p) == EXALT[p]:
            why.append("it is exalted in the Navamsa (D9)")
        out[p] = {"debilitated": True, "cancelled": bool(why), "reasons": why}
    return out


def yogas(signs: dict[str, int], lagna: int) -> list[dict]:
    asp, moon = aspects(signs, lagna), signs["Moon"]
    lord_of = lambda h: SIGN_LORDS[(lagna + h - 1) % 12]
    house = lambda p: _from(signs[p], lagna)
    together = lambda a, b: a != b and (signs[a] == signs[b] or (_sees(asp, a, b) and _sees(asp, b, a)))
    out = []

    def add(name, kind, planets, meaning):
        out.append({"name": name, "kind": kind, "planets": planets, "meaning": meaning})

    if _from(signs["Jupiter"], moon) in KENDRA:
        add("Gaja Kesari", "good", ["Jupiter", "Moon"], "Jupiter in a kendra from the Moon: wisdom, respect and protection.")
    if signs["Sun"] == signs["Mercury"]:
        add("Budha-Aditya", "good", ["Sun", "Mercury"], "Sun with Mercury: intelligence and communication skills.")
    if signs["Moon"] == signs["Mars"]:
        add("Chandra-Mangala", "good", ["Moon", "Mars"], "Moon with Mars: drive to earn and enterprising nature.")
    for p, name in MAHAPURUSHA.items():
        if house(p) in KENDRA and dignity(p, signs[p]) in ("own", "exalted"):
            add(f"{name} (Pancha Mahapurusha)", "good", [p], f"{p} strong in a kendra: its qualities shape your life prominently.")

    kendra_lords = {lord_of(h) for h in KENDRA}
    trikona_lords = {lord_of(h) for h in TRIKONA}
    for p in SEVEN:
        owned = [h for h in range(1, 13) if lord_of(h) == p]
        if any(h in (4, 7, 10) for h in owned) and any(h in (5, 9) for h in owned):
            add("Yogakaraka", "good", [p], f"{p} rules both a kendra and a trikona for your ascendant — your most helpful planet.")
    def pairs(group_a, group_b):
        found = []
        for x in group_a:
            for y in group_b:
                pair = tuple(sorted((x, y)))
                if x != y and pair not in found and together(x, y):
                    found.append(pair)
        return found

    raja = pairs(kendra_lords, trikona_lords)
    if raja:
        add("Raja yoga", "good", sorted({p for pr in raja for p in pr}),
            "Kendra and trikona lords join (" + "; ".join(" & ".join(pr) for pr in raja) + "): rise in status and success.")
    dhana = [pr for pr in pairs({lord_of(2), lord_of(11)}, {lord_of(1), lord_of(5), lord_of(9)}) if pr not in raja]
    if dhana:
        add("Dhana yoga", "good", sorted({p for pr in dhana for p in pr}),
            "Wealth lords join fortune lords (" + "; ".join(" & ".join(pr) for pr in dhana) + "): capacity to build money.")
    for h, name in ((6, "Harsha"), (8, "Sarala"), (12, "Vimala")):
        p = lord_of(h)
        if house(p) in DUSTHANA and house(p) != h:
            add(f"{name} (Viparita Raja)", "good", [p], f"The {h}th lord sits in another difficult house: setbacks tend to turn into gains.")

    others = [p for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")]
    flank = [p for p in others if _from(signs[p], moon) in (2, 12) or signs[p] == moon]
    if not flank:
        cancelled = _from(moon, lagna) in KENDRA or any(_from(signs[p], moon) in KENDRA for p in others)
        add("Kemadruma" + (" (cancelled)" if cancelled else ""), "neutral" if cancelled else "challenging", ["Moon"],
            "No planets beside the Moon: periods of feeling alone" + (", but other planets support the Moon, so it is largely cancelled." if cancelled else "; friendships and routine help."))

    r, k = signs["Rahu"], signs["Ketu"]
    side = lambda s: (s - r) % 12 < (k - r) % 12  # strictly on the Rahu→Ketu arc
    if all(signs[p] not in (r, k) for p in SEVEN):
        if all(side(signs[p]) for p in SEVEN) or not any(side(signs[p]) for p in SEVEN):
            add("Kaal Sarp", "challenging", ["Rahu", "Ketu"], "All planets lie on one side of the Rahu–Ketu axis: intense, karmic ups and downs; "
                "many astrologers consider it softened when planets are strong.")
    return out


def analyse(signs: dict[str, int], lagna: int, d9: dict[str, int] | None = None, combust: dict[str, bool] | None = None) -> dict:
    ys = yogas(signs, lagna)
    if combust and combust.get("Mercury"):
        for y in ys:
            if y["name"] == "Budha-Aditya":
                y["meaning"] = y["meaning"][:-1] + " (Mercury is combust, so it works more quietly)."
    return {"aspects": aspects(signs, lagna), "neecha_bhanga": neecha_bhanga(signs, lagna, d9), "yogas": ys}
