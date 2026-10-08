"""Ashtakoota (36-point) Guna Milan and Manglik check, computed from two natal chart dicts.

Inputs are the dicts returned by core.chart.compute_natal_chart. Guna Milan uses the Moon (sign,
nakshatra, degree); Manglik uses Mars from the lagna, Moon and Venus; the marriage promise uses the
KP 7th cusp sub lord. Tables follow the commonly published North-Indian
scheme; a few koota matrices differ slightly between schools, so results can vary by a point or two.
"""
from __future__ import annotations

from core import kp_predict

SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter",
             "Saturn", "Saturn", "Jupiter"]

# --- Varna (max 1): by Moon sign ---
VARNA_BY_SIGN = ["Kshatriya", "Vaishya", "Shudra", "Brahmin", "Kshatriya", "Vaishya",
                 "Shudra", "Brahmin", "Kshatriya", "Vaishya", "Shudra", "Brahmin"]
VARNA_RANK = {"Brahmin": 4, "Kshatriya": 3, "Vaishya": 2, "Shudra": 1}

# --- Vashya (max 2): groups by Moon sign (Sagittarius and Capricorn split at 15°) ---
VASHYA_ORDER = ["Chatushpada", "Nara", "Jalachara", "Vanachara", "Keeta"]
# rows = bride group, cols = groom group (order above)
VASHYA_POINTS = [
    [2, 1, 1, 0, 1],
    [1, 2, 0.5, 0, 1],
    [1, 0.5, 2, 1, 1],
    [0, 0, 1, 2, 0],
    [1, 0, 1, 0, 2],
]


def vashya_group(sign: int, deg: float) -> str:
    if sign in (0, 1):
        return "Chatushpada"
    if sign in (2, 5, 6, 10):
        return "Nara"
    if sign == 8:
        return "Nara" if deg < 15 else "Chatushpada"
    if sign == 9:
        return "Chatushpada" if deg < 15 else "Jalachara"
    if sign in (3, 11):
        return "Jalachara"
    if sign == 4:
        return "Vanachara"
    return "Keeta"  # Scorpio


# --- Tara (max 3) ---
TARA_NAMES = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyak", "Sadhana", "Naidhana", "Mitra", "Parama Mitra"]
TARA_BAD = {3, 5, 7}

# --- Yoni (max 4) ---
YONI_ORDER = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat", "Cow", "Buffalo", "Tiger",
              "Deer", "Monkey", "Mongoose", "Lion"]
YONI_BY_NAKSHATRA = ["Horse", "Elephant", "Sheep", "Serpent", "Serpent", "Dog", "Cat", "Sheep", "Cat",
                     "Rat", "Rat", "Cow", "Buffalo", "Tiger", "Buffalo", "Tiger", "Deer", "Deer", "Dog",
                     "Monkey", "Mongoose", "Monkey", "Lion", "Horse", "Lion", "Cow", "Elephant"]
YONI_POINTS = [
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1],
    [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1],
    [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1],
    [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2],
    [1, 2, 3, 1, 2, 2, 2, 4, 3, 0, 3, 2, 2, 1],
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1],
    [1, 1, 1, 2, 1, 1, 2, 0, 1, 4, 1, 1, 2, 1],
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1],
    [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2],
    [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4],
]

# --- Graha Maitri (max 5): natural friendship of the Moon-sign lords ---
FRIEND = {"Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"}, "Mars": {"Sun", "Moon", "Jupiter"},
          "Mercury": {"Sun", "Venus"}, "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
          "Saturn": {"Mercury", "Venus"}}
ENEMY = {"Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"}, "Mercury": {"Moon"},
         "Jupiter": {"Mercury", "Venus"}, "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"}}

# --- Gana (max 6) ---
GANA_BY_NAKSHATRA = ["Deva", "Manushya", "Rakshasa", "Manushya", "Deva", "Manushya", "Deva", "Deva",
                     "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva", "Rakshasa", "Deva",
                     "Rakshasa", "Deva", "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva",
                     "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva"]
GANA_POINTS = {("Deva", "Deva"): 6, ("Manushya", "Manushya"): 6, ("Rakshasa", "Rakshasa"): 6,
               ("Deva", "Manushya"): 5, ("Manushya", "Deva"): 5,
               ("Manushya", "Rakshasa"): 1, ("Rakshasa", "Manushya"): 1,
               ("Deva", "Rakshasa"): 0, ("Rakshasa", "Deva"): 0}  # keys: (bride, groom)

# --- Nadi (max 8) ---
NADI_BY_NAKSHATRA = ["Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi", "Adi", "Madhya", "Antya", "Antya",
                     "Madhya", "Adi", "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi", "Adi", "Madhya",
                     "Antya", "Antya", "Madhya", "Adi", "Adi", "Madhya", "Antya"]

MANGLIK_HOUSES = {1, 2, 4, 7, 8, 12}
# Mangal dosha bhanga: Mars in its own or exaltation sign anywhere, or in these signs in that house
# (counted from the lagna), does not give the dosha.
MARS_STRONG = {0: "own sign Aries", 7: "own sign Scorpio", 9: "exalted in Capricorn"}
MANGLIK_SIGN_EXCEPTIONS = {1: {4}, 2: {2, 5}, 7: {3}, 8: {8, 11}, 12: {1, 6}}
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius",
            "Capricorn", "Aquarius", "Pisces"]
# Plain-language areas of life each koota speaks to, for the strengths / friction summary.
AREA = {"Varna": "values and outlook", "Vashya": "give-and-take in the relationship",
        "Tara": "well-being and fortune together", "Yoni": "physical closeness",
        "Graha Maitri": "friendship and the way you think", "Gana": "temperament",
        "Bhakoot": "emotional bond, family and money", "Nadi": "health and children"}
GOOD_LINE = {"Varna": "You share similar values and outlook on life.",
             "Vashya": "There is natural attraction and easy give-and-take between you.",
             "Tara": "Your birth stars support each other's well-being and fortune.",
             "Yoni": "Good physical and intimate compatibility.",
             "Graha Maitri": "Your minds work well together — easy friendship and understanding.",
             "Gana": "Similar temperaments: you react to life in similar ways.",
             "Bhakoot": "A strong emotional bond with good support for family and finances.",
             "Nadi": "Different nadis — traditionally good for health and children."}
CLASH_LINE = {"Varna": "Different outlooks on life; respect each other's priorities.",
              "Vashya": "One may feel the other dominates; share decisions openly.",
              "Tara": "Your birth stars are not supportive of each other; take care of each other's health and mood.",
              "Yoni": "Physical and intimate needs may differ; talk about them early.",
              "Graha Maitri": "You think differently; misunderstandings need patient, clear talk.",
              "Gana": "Very different temperaments — one calmer, one more forceful; give each other space in arguments.",
              "Nadi": "Same nadi — traditionally a concern for health and children."}
BHAKOOT_LINE = {6: "Moon signs 6/8 apart — friction over everyday matters and health; patience is needed.",
                8: "Moon signs 6/8 apart — friction over everyday matters and health; patience is needed.",
                2: "Moon signs 2/12 apart — money and spending habits can differ; plan finances together.",
                12: "Moon signs 2/12 apart — money and spending habits can differ; plan finances together.",
                5: "Moon signs 5/9 apart — different views on children, faith or long-term plans.",
                9: "Moon signs 5/9 apart — different views on children, faith or long-term plans."}


def _moon(chart: dict) -> dict:
    m = chart["grahas"]["Moon"]
    return {"sign": m["sign"], "sign_index": m["sign_index"], "deg": m["degrees_in_sign"],
            "nak": m["nakshatra"], "nak_index": m["nakshatra_index"], "pada": m["pada"]}


def _rel(a: str, b: str) -> str:
    if a == b or b in FRIEND[a]:
        return "friend"
    if b in ENEMY[a]:
        return "enemy"
    return "neutral"


def _maitri(bride_lord: str, groom_lord: str) -> float:
    if bride_lord == groom_lord:
        return 5
    r = sorted([_rel(bride_lord, groom_lord), _rel(groom_lord, bride_lord)])
    return {("friend", "friend"): 5, ("friend", "neutral"): 4, ("neutral", "neutral"): 3,
            ("enemy", "friend"): 1, ("enemy", "neutral"): 0.5, ("enemy", "enemy"): 0}[tuple(r)]


def _tara(from_idx: int, to_idx: int) -> tuple[int, bool]:
    n = (to_idx - from_idx) % 27 + 1
    rem = n % 9 or 9
    return rem, rem in TARA_BAD




def _from(sign: int, base: int) -> int:
    return (sign - base) % 12 + 1


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def manglik(chart: dict) -> dict:
    """Mars in 1, 2, 4, 7, 8 or 12 counted from the lagna, the Moon and Venus; then the classical exceptions."""
    g, lagna = chart["grahas"], chart["lagna"]["sign_index"]
    mars = g["Mars"]["sign_index"]
    refs = [{"from": name, "house": _from(mars, base)} for name, base in
            (("Lagna", lagna), ("Moon", g["Moon"]["sign_index"]), ("Venus", g["Venus"]["sign_index"]))]
    hits = [r["from"] for r in refs if r["house"] in MANGLIK_HOUSES]
    level = ["none", "mild", "moderate", "strong"][len(hits)]
    cancels, reduces = [], []
    if hits:
        hl = refs[0]["house"]
        if mars in MARS_STRONG:
            cancels.append(f"Mars is in its {MARS_STRONG[mars]}")
        if mars in MANGLIK_SIGN_EXCEPTIONS.get(hl, ()):
            cancels.append(f"Mars in {SIGNS_EN[mars]} in the {_ord(hl)} house is a classical exception")
        jh = _from(mars, g["Jupiter"]["sign_index"])
        if jh in (1, 5, 7, 9):
            reduces.append("Jupiter is with Mars" if jh == 1 else "Jupiter aspects Mars")
    order = ["none", "mild", "moderate", "strong"]
    effective = "none" if cancels else order[max(0, order.index(level) - len(reduces))]
    return {"mars_house_from_lagna": refs[0]["house"], "mars_house_from_moon": refs[1]["house"],
            "references": refs, "hits": hits, "manglik": bool(hits), "level": level,
            "exceptions": cancels + reduces, "cancelled": bool(cancels), "effective": effective}


def _saturn_balance(chart: dict) -> int | None:
    """Saturn in 1, 4, 7, 8 or 12 from the lagna is traditionally held to balance a partner's Mangal dosha."""
    h = _from(chart["grahas"]["Saturn"]["sign_index"], chart["lagna"]["sign_index"])
    return h if h in (1, 4, 7, 8, 12) else None


def _manglik_match(groom: dict, bride: dict, mg: dict, mb: dict) -> dict:
    eg, eb = mg["effective"] != "none", mb["effective"] != "none"
    tail = "".join(f" The {w}'s Mars dosha is {'cancelled' if m['cancelled'] else 'eased'} "
                   f"({'; '.join(m['exceptions'])})." for w, m in (("groom", mg), ("bride", mb))
                   if m["manglik"] and m["effective"] == "none")
    if eg and eb:
        return {"status": "balanced", "text": "Both partners are Manglik, which traditionally balances the dosha." + tail}
    if not eg and not eb:
        return {"status": "none", "text": "No Manglik concern for this match." + tail}
    who, m, other = ("groom", mg, bride) if eg else ("bride", mb, groom)
    sat = _saturn_balance(other)
    if sat:
        return {"status": "balanced", "text": f"The {who} is Manglik ({m['effective']}); the partner's Saturn in the "
                f"{_ord(sat)} house traditionally balances it." + tail}
    if m["effective"] == "mild":
        return {"status": "minor", "text": f"The {who} is mildly Manglik (Mars from one reference point only). "
                "A small concern; simple Mangal upay are usually enough." + tail}
    return {"status": "concern", "text": f"The {who} is {m['effective']}ly Manglik and the partner is not. Traditionally "
            "this needs a closer look and remedies before going ahead." + tail}


def _doshas(g: dict, b: dict, kootas: dict) -> list[dict]:
    """Nadi, Bhakoot and Gana dosha with the common cancellation (parihar) rules."""
    gl, bl = SIGN_LORD[g["sign_index"]], SIGN_LORD[b["sign_index"]]
    friends = _maitri(bl, gl) == 5
    same_sign = g["sign_index"] == b["sign_index"]
    out = []
    if kootas["Nadi"]["got"] == 0:
        if g["nak_index"] == b["nak_index"] and not same_sign:
            st, why = "cancelled", "same nakshatra but different Moon signs"
        elif same_sign and g["nak_index"] != b["nak_index"]:
            st, why = "cancelled", "same Moon sign but different nakshatras"
        elif gl == bl and not same_sign:
            st, why = "cancelled", f"both Moon signs are ruled by {gl}"
        elif g["nak_index"] == b["nak_index"]:
            st, why = (("reduced", "same nakshatra but a different pada") if g["pada"] != b["pada"]
                       else ("present", "same nakshatra and pada — its strongest form"))
        elif friends:
            st, why = "reduced", f"the Moon-sign lords {bl} and {gl} are friends"
        else:
            st, why = "present", "no cancelling factor"
        out.append({"name": "Nadi Dosha", "koota": "Nadi", "status": st, "severity": "major", "why": why})
    if kootas["Bhakoot"]["got"] == 0:
        d = (g["sign_index"] - b["sign_index"]) % 12 + 1
        sev = "major" if d in (6, 8) else "moderate" if d in (2, 12) else "minor"
        pair = f"{min(d, 14 - d)}/{max(d, 14 - d)}"
        if gl == bl:
            st, why = "cancelled", f"both Moon signs are ruled by {gl}"
        elif friends:
            st, why = "cancelled", f"the Moon-sign lords {bl} and {gl} are mutual friends"
        elif _maitri(bl, gl) >= 4:
            st, why = "reduced", f"the Moon-sign lords {bl} and {gl} are friendly"
        else:
            st, why = "present", "no cancelling factor"
        out.append({"name": f"Bhakoot Dosha ({pair})", "koota": "Bhakoot", "status": st, "severity": sev, "why": why,
                    "distance": d})
    if kootas["Gana"]["got"] <= 1:
        bhakoot_ok = kootas["Bhakoot"]["got"] == 7 or any(x["koota"] == "Bhakoot" and x["status"] == "cancelled" for x in out)
        if _maitri(bl, gl) >= 4 and bhakoot_ok:
            st, why = "cancelled", "the Moon-sign lords are friendly and Bhakoot is good"
        else:
            st, why = "present", "no cancelling factor"
        out.append({"name": "Gana Dosha", "koota": "Gana", "status": st,
                    "severity": "moderate" if kootas["Gana"]["got"] == 0 else "minor", "why": why})
    return out


def marriage_promise(chart: dict) -> dict | None:
    """KP / Nadi: is marriage promised (7th cusp sub lord), and is separation indicated?"""
    houses = chart.get("houses") or []
    if len(houses) < 12 or "kp" not in houses[6]:
        return None
    p, sep = kp_predict.promise(chart, "marriage"), kp_predict.promise(chart, "divorce")
    return {"verdict": p["verdict"], "cusp_sub_lord": p["cusp_sub_lord"], "star_lord": p["csl_star_lord"],
            "signifies": p["signifies"], "for": p["for"], "against": p["against"], "separation": sep["verdict"]}


TIER = {"good": "Good match", "care": "Workable with care", "think": "Think carefully"}


def _overall(adjusted: float, doshas: list[dict], mm: dict, promises: list[tuple[str, dict | None]]) -> dict:
    live = [d for d in doshas if d["status"] != "cancelled"]
    major = [d for d in live if d["severity"] == "major" and d["status"] == "present"]
    other = [d for d in live if d not in major and d["severity"] != "minor"]
    weak = [w for w, p in promises if p and p["verdict"] == "not clearly promised"]
    serious = len(major) + (mm["status"] == "concern") + len(weak)
    if adjusted < 18 or serious >= 2:
        tier = "think"
    elif adjusted >= 24 and not serious and not other and mm["status"] != "minor":
        tier = "good"
    else:
        tier = "care"
    bits = [f"{adjusted:g}/36 after dosha cancellations"]
    bits.append("unresolved " + " and ".join(d["name"] for d in major + other) if major + other else "no unresolved major dosha")
    if mm["status"] == "concern":
        bits.append("a Manglik mismatch")
    known = [p for _, p in promises if p]
    odd = [(w, p["verdict"]) for w, p in promises if p and p["verdict"] != "promised"]
    if odd:
        bits.append("marriage " + " and ".join(f"is {v} in the {w}'s chart" for w, v in odd))
    elif known:
        bits.append("marriage is promised in both charts" if len(known) == 2 else "marriage is promised in the chart we could check")
    return {"tier": tier, "label": TIER[tier], "summary": "; ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1] + "."}


def _strengths_clashes(kootas: list[dict], doshas: list[dict], mm: dict,
                       promises: list[tuple[str, dict | None]]) -> tuple[list[dict], list[dict]]:
    by_koota = {d["koota"]: d for d in doshas}
    good, bad = [], []
    for k in sorted(kootas, key=lambda k: -k["max"]):
        ratio, dz = k["got"] / k["max"], by_koota.get(k["name"])
        if dz and dz["status"] == "cancelled":
            continue
        if ratio >= 0.75:
            good.append({"area": AREA[k["name"]], "text": GOOD_LINE[k["name"]]})
        elif ratio <= 0.25:
            text = BHAKOOT_LINE[dz["distance"]] if k["name"] == "Bhakoot" else CLASH_LINE[k["name"]]
            if dz and dz["status"] == "reduced":
                text += f" Softened because {dz['why']}."
            bad.append({"area": AREA[k["name"]], "text": text})
    known = [(w, p) for w, p in promises if p]
    if len(known) == 2 and all(p["verdict"] == "promised" for _, p in known):
        good.insert(0, {"area": "marriage promise", "text": "Marriage is clearly promised in both charts."})
    for w, p in known:
        if p["verdict"] == "not clearly promised":
            bad.insert(0, {"area": "marriage promise", "text": f"Marriage is not clearly promised in the {w}'s chart; "
                           "timing and a careful reading of the 7th house matter more here."})
        elif p["separation"] == "indicated":
            bad.append({"area": "staying together", "text": f"The {w}'s chart asks for extra care to keep harmony in "
                        "marriage; patience and open talk help."})
    if mm["status"] in ("concern", "minor"):
        bad.append({"area": "Mangal dosha", "text": mm["text"]})
    return good[:4], bad[:4]


def _verdict(total: float) -> str:
    if total >= 33:
        return "Excellent match"
    if total >= 25:
        return "Very good match"
    if total >= 18:
        return "Acceptable match"
    return "Below the usual 18-point minimum"


def compute_match(groom: dict, bride: dict) -> dict:
    g, b = _moon(groom), _moon(bride)
    kootas = []

    gv, bv = VARNA_BY_SIGN[g["sign_index"]], VARNA_BY_SIGN[b["sign_index"]]
    kootas.append({"name": "Varna", "max": 1, "got": 1 if VARNA_RANK[gv] >= VARNA_RANK[bv] else 0,
                   "groom": gv, "bride": bv, "meaning": "Ego and spiritual compatibility"})

    gva, bva = vashya_group(g["sign_index"], g["deg"]), vashya_group(b["sign_index"], b["deg"])
    kootas.append({"name": "Vashya", "max": 2, "got": VASHYA_POINTS[VASHYA_ORDER.index(bva)][VASHYA_ORDER.index(gva)],
                   "groom": gva, "bride": bva, "meaning": "Mutual attraction and influence"})

    r1, bad1 = _tara(b["nak_index"], g["nak_index"])
    r2, bad2 = _tara(g["nak_index"], b["nak_index"])
    kootas.append({"name": "Tara", "max": 3, "got": 3 if not (bad1 or bad2) else 1.5 if not (bad1 and bad2) else 0,
                   "groom": TARA_NAMES[r2 - 1], "bride": TARA_NAMES[r1 - 1],
                   "meaning": "Health, well-being and destiny together"})

    gy, by = YONI_BY_NAKSHATRA[g["nak_index"]], YONI_BY_NAKSHATRA[b["nak_index"]]
    kootas.append({"name": "Yoni", "max": 4, "got": YONI_POINTS[YONI_ORDER.index(by)][YONI_ORDER.index(gy)],
                   "groom": gy, "bride": by, "meaning": "Physical and intimate compatibility"})

    gl, bl = SIGN_LORD[g["sign_index"]], SIGN_LORD[b["sign_index"]]
    kootas.append({"name": "Graha Maitri", "max": 5, "got": _maitri(bl, gl), "groom": gl, "bride": bl,
                   "meaning": "Mental wavelength and friendship"})

    gg, bg = GANA_BY_NAKSHATRA[g["nak_index"]], GANA_BY_NAKSHATRA[b["nak_index"]]
    kootas.append({"name": "Gana", "max": 6, "got": GANA_POINTS[(bg, gg)], "groom": gg, "bride": bg,
                   "meaning": "Temperament and nature"})

    d = (g["sign_index"] - b["sign_index"]) % 12 + 1
    bad_bhakoot = d in (2, 12, 5, 9, 6, 8)
    kootas.append({"name": "Bhakoot", "max": 7, "got": 0 if bad_bhakoot else 7,
                   "groom": g["sign"], "bride": b["sign"],
                   "meaning": f"Emotional bond, family welfare and finances (Moon signs are {d} apart)"})

    gn, bn = NADI_BY_NAKSHATRA[g["nak_index"]], NADI_BY_NAKSHATRA[b["nak_index"]]
    kootas.append({"name": "Nadi", "max": 8, "got": 0 if gn == bn else 8, "groom": gn, "bride": bn,
                   "meaning": "Health and progeny; the same nadi is considered a dosha"})

    total = sum(k["got"] for k in kootas)
    by_name = {k["name"]: k for k in kootas}
    doshas = _doshas(g, b, by_name)
    adjusted = total + sum(by_name[x["koota"]]["max"] - by_name[x["koota"]]["got"]
                           for x in doshas if x["status"] == "cancelled")
    mg, mb = manglik(groom), manglik(bride)
    mm = _manglik_match(groom, bride, mg, mb)
    pg, pb = marriage_promise(groom), marriage_promise(bride)
    promises = [("groom", pg), ("bride", pb)]
    strengths, clashes = _strengths_clashes(kootas, doshas, mm, promises)
    notes = [f"{x['name']}: {x['status']} — {x['why']}." for x in doshas]
    return {
        "total": total, "adjusted_total": adjusted, "max": 36, "verdict": _verdict(total),
        "overall": _overall(adjusted, doshas, mm, promises), "strengths": strengths, "clashes": clashes,
        "kootas": kootas, "doshas": doshas, "manglik": mm,
        "groom": {"name": groom["meta"].get("name") or "Groom", "moon_sign": g["sign"], "nakshatra": g["nak"],
                  "pada": g["pada"], "manglik": mg, "promise": pg},
        "bride": {"name": bride["meta"].get("name") or "Bride", "moon_sign": b["sign"], "nakshatra": b["nak"],
                  "pada": b["pada"], "manglik": mb, "promise": pb},
        "manglik_note": mm["text"], "notes": notes,
        "disclaimer": "Guna Milan, dosha cancellations and Manglik rules follow common North-Indian practice; "
                      "schools differ on some tables and exceptions. The marriage promise uses the KP 7th cusp "
                      "sub lord. Traditional guidance, not certainty.",
    }
