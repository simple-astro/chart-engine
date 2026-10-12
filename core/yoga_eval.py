"""Yogas with the three checks every yoga needs before it is read (owner's research, 2026-10-12):

1. Net strength — are the yoga's planets combust, debilitated without Neecha Bhanga, or joined with the lords of
   the 6th, 8th or 12th? Then the yoga works at reduced strength.
2. Dasha activation — a yoga stays dormant until the Mahadasha or Antardasha of one of its planets runs.
3. Cancellation (yoga bhanga) — the classical rules that nullify Raja yogas: the Sun at 6-10 deg Libra (deep
   debilitation); a debilitated Moon while the Sun, Mars, Jupiter or Saturn sits in the Lagna; a Mahapurusha planet
   joined by the Sun or Moon; the 9th or 10th lord combust or debilitated.

The catalogue is core.yogas (already used by Sukh and the fact-check) plus the yogas below, all from whole-sign
positions, so the drawn chart, the Yogas tab, Sukh and the fact-check agree. Wording stays gentle: challenging
yogas are framed as patterns to handle, never as fate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core import yogas as Y
from core.constants import SIGN_LORDS
from core.dignity import dignity

BENEFICS = ("Mercury", "Jupiter", "Venus")
MALEFICS = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")
NO_LUM = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")  # the five used for Moon- and Sun-flanking yogas
CATEGORY = {"Pancha Mahapurusha": "Pancha Mahapurusha", "Raja yoga": "Raja", "Yogakaraka": "Raja",
            "Dharma-Karmadhipati": "Raja", "Kahala": "Raja", "Chamara": "Raja", "Lagnadhi": "Raja", "Adhi": "Raja",
            "Viparita Raja": "Viparita Raja", "Dhana yoga": "Wealth", "Lakshmi": "Wealth", "Vasumati": "Wealth",
            "Chandra-Mangala": "Wealth", "Gaja Kesari": "Moon", "Sunapha": "Moon", "Anapha": "Moon",
            "Durudhara": "Moon", "Amala": "Moon", "Kemadruma": "Moon", "Shakata": "Moon", "Budha-Aditya": "Sun",
            "Vesi": "Sun", "Vosi": "Sun", "Ubhayachari": "Sun", "Saraswati": "Wisdom", "Pravrajya": "Spiritual",
            "Tapaswi": "Spiritual", "Moksha": "Spiritual", "Mala": "Pattern", "Sarpa": "Pattern", "Gada": "Pattern",
            "Sringataka": "Pattern", "Hala": "Pattern", "Chakra": "Pattern", "Kaal Sarp": "Challenge",
            "Guru-Chandal": "Challenge", "Grahan": "Challenge", "Angarak": "Challenge", "Punarphoo": "Challenge",
            "Daridra": "Challenge"}
ORDER = ["Pancha Mahapurusha", "Raja", "Viparita Raja", "Wealth", "Wisdom", "Moon", "Sun", "Spiritual", "Pattern",
         "Challenge"]
RAJA_LIKE = {"Pancha Mahapurusha", "Raja", "Wealth"}


def _cat(name: str) -> str:
    for key, cat in CATEGORY.items():
        if key in name:
            return cat
    return "Raja"


def extra_yogas(signs: dict[str, int], lagna: int) -> list[dict]:
    """The yogas of the reference manual that core.yogas does not already find."""
    f = Y._from
    asp = Y.aspects(signs, lagna)
    moon, sun = signs["Moon"], signs["Sun"]
    lord_of = lambda h: SIGN_LORDS[(lagna + h - 1) % 12]
    house = lambda p: f(signs[p], lagna)
    joined = lambda a, b: a != b and (signs[a] == signs[b] or (Y._sees(asp, a, b) and Y._sees(asp, b, a))
                                      or (SIGN_LORDS[signs[a]] == b and SIGN_LORDS[signs[b]] == a))
    strong = lambda p: dignity(p, signs[p]) in ("exalted", "own")
    out = []

    def add(name, kind, planets, meaning):
        out.append({"name": name, "kind": kind, "planets": list(dict.fromkeys(planets)), "meaning": meaning})

    # Raja
    l9, l10 = lord_of(9), lord_of(10)
    if l9 != l10 and joined(l9, l10):
        add("Dharma-Karmadhipati", "good", [l9, l10], f"Your 9th lord {l9} and 10th lord {l10} are linked: steady rise, "
            "honour and work that feels meaningful.")
    l1, l4 = lord_of(1), lord_of(4)
    if l4 != l9 and f(signs[l9], signs[l4]) in Y.KENDRA and strong(l1):
        add("Kahala", "good", [l4, l9, l1], "4th and 9th lords in kendras from each other with a strong Lagna lord: "
            "courage and the ability to lead a team.")
    if dignity(l1, signs[l1]) == "exalted" and house(l1) in Y.KENDRA and "Jupiter" != l1 and Y._sees(asp, "Jupiter", l1):
        add("Chamara", "good", [l1, "Jupiter"], "An exalted Lagna lord in a kendra, seen by Jupiter: respected learning "
            "and leadership.")
    for base, name in ((lagna, "Lagnadhi"), (moon, "Adhi (from the Moon)")):
        if all(f(signs[p], base) in (6, 7, 8) for p in BENEFICS):
            add(name, "good", list(BENEFICS), "Mercury, Jupiter and Venus all in the 6th, 7th and 8th: support from "
                "people around you, success over rivals and a position of trust.")
    # Wealth
    l1_ok = dignity(l1, signs[l1]) in ("exalted", "own", "friendly") or house(l1) in Y.KENDRA + Y.TRIKONA
    if house(l9) in Y.KENDRA + Y.TRIKONA and strong(l9) and l1_ok:
        add("Lakshmi", "good", [l9, l1], f"Your 9th lord {l9} is strong in a kendra or trikona: grace, comfort and "
            "lasting prosperity.")
    for base, where in ((lagna, "the Lagna"), (moon, "the Moon")):
        if all(f(signs[p], base) in (3, 6, 10, 11) for p in BENEFICS):
            add(f"Vasumati (from {where})", "good", list(BENEFICS), "Mercury, Jupiter and Venus all in growth houses: "
                "wealth built by your own effort.")
            break
    # Moon
    two = [p for p in NO_LUM if f(signs[p], moon) == 2]
    twelve = [p for p in NO_LUM if f(signs[p], moon) == 12]
    if two and twelve:
        add("Durudhara", "good", ["Moon"] + two + twelve, "Planets on both sides of the Moon: a steady mind, "
            "generosity and comforts.")
    elif two:
        add("Sunapha", "good", ["Moon"] + two, "Planets in the 2nd from the Moon: self-made wealth and good judgement.")
    elif twelve:
        add("Anapha", "good", ["Moon"] + twelve, "Planets in the 12th from the Moon: contentment, good manners and "
            "inner peace.")
    amala = [p for p in BENEFICS if house(p) == 10 or f(signs[p], moon) == 10]
    if amala:
        add("Amala", "good", amala, "A benefic in the 10th: a clean reputation and work people respect.")
    if f(moon, signs["Jupiter"]) in (6, 8, 12):
        eased = house("Moon") in Y.KENDRA
        add("Shakata" + (" (eased)" if eased else ""), "neutral" if eased else "challenging", ["Moon", "Jupiter"],
            "The Moon in the 6th, 8th or 12th from Jupiter: fortunes rise and dip like a wheel — keep savings steady"
            + (", and the Moon in a kendra eases it." if eased else "."))
    # Sun
    v2 = [p for p in NO_LUM if p != "Sun" and f(signs[p], sun) == 2]
    v12 = [p for p in NO_LUM if p != "Sun" and f(signs[p], sun) == 12]
    if v2 and v12:
        add("Ubhayachari", "good", ["Sun"] + v2 + v12, "Planets on both sides of the Sun: poise, ability and popularity.")
    elif v2:
        add("Vesi", "good", ["Sun"] + v2, "A planet in the 2nd from the Sun: balanced views and steady earnings.")
    elif v12:
        add("Vosi", "good", ["Sun"] + v12, "A planet in the 12th from the Sun: generosity, good memory and skill.")
    # Wisdom
    good_houses = Y.KENDRA + Y.TRIKONA + (2,)
    if all(house(p) in good_houses for p in BENEFICS) and dignity("Jupiter", signs["Jupiter"]) != "debilitated":
        add("Saraswati", "good", list(BENEFICS), "Jupiter, Venus and Mercury well placed: learning, writing and the arts.")
    # Spiritual
    for s in set(signs.values()):
        group = [p for p in Y.SEVEN if signs[p] == s]
        if len(group) >= 4:
            add("Pravrajya", "neutral", group, f"{len(group)} planets in one sign: a strong pull toward one path in life, "
                "often study, service or spiritual practice.")
    if joined("Saturn", "Venus") and joined("Saturn", "Mars") and joined("Venus", "Mars"):
        add("Tapaswi", "neutral", ["Saturn", "Venus", "Mars"], "Saturn, Venus and Mars linked: discipline and devotion "
            "to one noble pursuit.")
    if house("Ketu") == 12:
        add("Moksha", "neutral", ["Ketu"], "Ketu in the 12th: a natural pull toward spiritual life and letting go.")
    # Patterns of all seven planets (Nabhasa)
    hs = {p: house(p) for p in Y.SEVEN}
    if set(hs.values()) <= set(Y.TRIKONA):
        add("Sringataka", "good", list(Y.SEVEN), "All planets in trikonas: good fortune, intelligence and a happy home.")
    if any(set(hs.values()) <= g for g in ({2, 6, 10}, {3, 7, 11}, {4, 8, 12})):
        add("Hala", "neutral", list(Y.SEVEN), "All planets in one earth-like triad: hard work that builds prosperity.")
    if set(hs.values()) <= {1, 3, 5, 7, 9, 11}:
        add("Chakra", "good", list(Y.SEVEN), "All planets in alternate houses from the Lagna: rank and respect.")
    for a, b in ((1, 4), (4, 7), (7, 10), (10, 1)):
        if set(hs.values()) <= {a, b}:
            add("Gada", "good", list(Y.SEVEN), "All planets in two neighbouring kendras: wealth and steady skill.")
    natb = [p for p in Y.SEVEN if p in BENEFICS]
    natm = [p for p in Y.SEVEN if p in ("Sun", "Mars", "Saturn")]
    if all(hs[p] in Y.KENDRA for p in natb) and not any(hs[p] in Y.KENDRA for p in natm):
        add("Mala", "good", natb, "All benefics in kendras: comfort, health and support.")
    if all(hs[p] in Y.KENDRA for p in natm) and not any(hs[p] in Y.KENDRA for p in natb):
        add("Sarpa", "challenging", natm, "All malefics in kendras: life asks for patience and steady effort.")
    # Challenges (gentle)
    for node in ("Rahu", "Ketu"):
        if signs["Jupiter"] == signs[node]:
            add("Guru-Chandal", "challenging", ["Jupiter", node], f"Jupiter with {node}: unusual beliefs and questions "
                "about tradition — choose teachers carefully.")
        for lum in ("Sun", "Moon"):
            if signs[lum] == signs[node]:
                add(f"Grahan ({lum})", "challenging", [lum, node], f"The {lum} with {node}: times of self-doubt; "
                    "steady routines and good company help.")
        if signs["Mars"] == signs[node]:
            add("Angarak", "challenging", ["Mars", node], f"Mars with {node}: strong, impatient energy — channel it into "
                "sport or hard work and drive with care.")
    if signs["Saturn"] == signs["Moon"] or (Y._sees(asp, "Saturn", "Moon") and Y._sees(asp, "Moon", "Saturn")):
        add("Punarphoo", "challenging", ["Saturn", "Moon"], "Saturn and the Moon linked: delays and second thoughts "
            "before commitments — decide with patience.")
    l11 = lord_of(11)
    if house(l11) in Y.DUSTHANA and l11 not in (lord_of(6), lord_of(8), lord_of(12)):
        add("Daridra", "challenging", [l11], f"Your 11th lord {l11} sits in a difficult house: income needs steady effort "
            "and careful saving.")
    return out


def jaimini_yogas(chart: dict) -> list[dict]:
    """AK with AmK, PK or DK by conjunction or Jaimini sign aspect (8 karakas, the owner's scheme)."""
    from core import chara, jaimini
    j = chart.get("jaimini") or jaimini.analyse(chart)
    by = {k["short"]: k["planet"] for k in j["karakas"]}
    signs = {p: v["sign_index"] for p, v in chart["grahas"].items()}
    linked = lambda a, b: signs[a] == signs[b] or signs[b] in chara.rashi_aspects(signs[a])
    out = []
    for k, text in (("AmK", "your soul planet and career planet linked: a career that rises with purpose"),
                    ("PK", "your soul planet and children/creativity planet linked: intelligence and creative mastery"),
                    ("DK", "your soul planet and partner planet linked: rise through marriage and partnerships")):
        ak, other = by.get("AK"), by.get(k)
        if ak and other and ak != other and linked(ak, other):
            out.append({"name": f"AK-{k} (Jaimini)", "kind": "good", "planets": [ak, other],
                        "meaning": f"{ak} (AK) with {other} ({k}): {text}."})
    return out


def _dusthana_lords(lagna: int) -> set[str]:
    """Planets that rule the 6th, 8th or 12th and no kendra or trikona (a 5th-and-12th lord is not counted)."""
    owned: dict[str, set[int]] = {}
    for h in range(1, 13):
        owned.setdefault(SIGN_LORDS[(lagna + h - 1) % 12], set()).add(h)
    return {p for p, hs in owned.items() if hs & {6, 8, 12} and not hs & {1, 4, 5, 7, 9, 10}}


def _combust(g: dict, p: str) -> bool:
    """Combustion that weakens a yoga. Mercury is nearly always near the Sun, so (as the reference itself says for
    Budha-Aditya) only Mercury within 3 deg of the Sun counts."""
    if not g[p].get("combust"):
        return False
    if p != "Mercury":
        return True
    d = abs(g["Mercury"]["longitude"] - g["Sun"]["longitude"]) % 360
    return min(d, 360 - d) < 3


def evaluate(chart: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    g, lagna = chart["grahas"], chart["lagna"]["sign_index"]
    signs = {p: v["sign_index"] for p, v in g.items()}
    d9 = {p: v["sign_index"] for p, v in chart.get("vargas", {}).get("D9", {}).items()} or None
    nb = Y.neecha_bhanga(signs, lagna, d9)
    asp = Y.aspects(signs, lagna)
    found = Y.yogas(signs, lagna) + extra_yogas(signs, lagna) + jaimini_yogas(chart)
    lord_of = lambda h: SIGN_LORDS[(lagna + h - 1) % 12]
    dus = _dusthana_lords(lagna)
    # Classical yoga bhanga that nullifies Raja-type yogas for the whole chart (the two strongest rules only)
    bhanga = []
    if signs["Sun"] == 6 and 6 <= g["Sun"]["degrees_in_sign"] <= 10:
        bhanga.append("the Sun is in deep debilitation (6–10° Libra)")
    if signs["Moon"] == 7 and any(Y._from(signs[p], lagna) == 1 for p in ("Sun", "Mars", "Jupiter", "Saturn")):
        bhanga.append("a debilitated Moon while the Sun, Mars, Jupiter or Saturn sits in the Lagna")
    # A weak 9th or 10th lord weakens the yogas it takes part in
    weak_lords = {}
    for h in (9, 10):
        L = lord_of(h)
        if _combust(g, L):
            weak_lords[L] = f"your {h}th lord {L} is combust"
        elif dignity(L, signs[L]) == "debilitated" and not nb.get(L, {}).get("cancelled"):
            weak_lords[L] = f"your {h}th lord {L} is debilitated"
    # Running dasha lords and the next start of each lord (maha or antar), from the chart's own tree
    iso = now.isoformat()
    running, nexts = {}, {}
    for md in chart.get("dasha", []):
        if md["start"] <= iso < md["end"]:
            running["Mahadasha"] = md["lord"]
        if md["start"] > iso:
            nexts.setdefault(md["lord"], ("Mahadasha", md["start"]))
        for ad in md.get("children") or []:
            if ad["start"] <= iso < ad["end"]:
                running["Antardasha"] = ad["lord"]
            if ad["start"] > iso:
                nexts.setdefault(ad["lord"], (f"{md['lord']}–{ad['lord']} Antardasha", ad["start"]))
    out = []
    for y in found:
        cat = _cat(y["name"])
        planets = [p for p in y["planets"] if p in g]
        notes = []
        for p in planets:
            if _combust(g, p):
                notes.append(f"{p} is combust")
            if dignity(p, signs[p]) == "debilitated":
                notes.append(f"{p} is debilitated" + (" (cancelled by Neecha Bhanga)" if nb.get(p, {}).get("cancelled") else ""))
            touch = [d for d in dus if d != p and d not in planets and (signs[d] == signs[p] or Y._sees(asp, d, p))]
            if touch and cat in RAJA_LIKE:
                notes.append(f"{p} is touched by {', '.join(sorted(touch))} (a 6th/8th/12th lord)")
        for p in planets:
            if p in weak_lords and cat in RAJA_LIKE and weak_lords[p] not in notes and f"{p} is combust" not in notes:
                notes.append(weak_lords[p])
        if cat == "Pancha Mahapurusha":
            p = planets[0]
            for lum in ("Sun", "Moon"):
                if signs[lum] == signs[p]:
                    notes.append(f"the {lum} sits with {p}, dimming it")
        status, cancel = "Strong", []
        if cat in RAJA_LIKE and bhanga:
            status, cancel = "Cancelled", list(bhanga)
        elif y["kind"] == "good":
            hard = [n for n in notes if "cancelled by" not in n]
            status = "Strong" if not hard else "Mixed" if len(hard) == 1 else "Weak"
        elif y["kind"] == "neutral" or "(cancelled)" in y["name"] or "(eased)" in y["name"]:
            status = "Eased" if "(cancelled)" in y["name"] or "(eased)" in y["name"] else "Present"
        else:
            status = "Present"
        lifelong = cat == "Pattern"
        act = next((f"{lvl} of {lord}" for lvl, lord in running.items() if lord in planets), None)
        upcoming = sorted((nexts[p][1], nexts[p][0], p) for p in planets if p in nexts)
        out.append({**y, "category": cat, "status": status, "notes": notes, "cancelled_by": cancel,
                    "active": bool(act), "active_by": act, "lifelong": lifelong,
                    "next": None if act or lifelong or not upcoming else
                    {"date": upcoming[0][0][:10], "period": upcoming[0][1], "planet": upcoming[0][2]}})
    out.sort(key=lambda y: (ORDER.index(y["category"]), not y["active"], y["name"]))
    return {"yogas": out, "bhanga": bhanga, "running": running,
            "counts": {"good": sum(y["kind"] == "good" for y in out), "challenging": sum(y["kind"] == "challenging" for y in out),
                       "active": sum(y["active"] for y in out)}}
