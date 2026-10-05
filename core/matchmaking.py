"""Ashtakoota (36-point) Guna Milan and Manglik check, computed from two natal chart dicts.

Inputs are the dicts returned by core.chart.compute_natal_chart. Only the Moon (sign, nakshatra,
degree) and Mars/lagna positions are used. Tables follow the commonly published North-Indian
scheme; a few koota matrices differ slightly between schools, so results can vary by a point or two.
"""
from __future__ import annotations

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


def manglik(chart: dict) -> dict:
    lagna = chart["lagna"]["sign_index"]
    moon = chart["grahas"]["Moon"]["sign_index"]
    mars = chart["grahas"]["Mars"]["sign_index"]
    from_lagna = (mars - lagna) % 12 + 1
    from_moon = (mars - moon) % 12 + 1
    hit_l, hit_m = from_lagna in MANGLIK_HOUSES, from_moon in MANGLIK_HOUSES
    level = "high" if hit_l and hit_m else "partial" if hit_l or hit_m else "none"
    return {"mars_house_from_lagna": from_lagna, "mars_house_from_moon": from_moon,
            "manglik": hit_l or hit_m, "level": level}


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
    mg, mb = manglik(groom), manglik(bride)
    if mg["manglik"] and mb["manglik"]:
        mnote = "Both partners are Manglik, which traditionally balances the dosha."
    elif mg["manglik"] or mb["manglik"]:
        who = "groom" if mg["manglik"] else "bride"
        mnote = (f"Only the {who} is Manglik. Traditionally this calls for a closer look at Mars in both "
                 "charts and, often, remedies or a Manglik partner.")
    else:
        mnote = "Neither partner is Manglik."
    notes = []
    if kootas[7]["got"] == 0:
        notes.append("Nadi dosha: both share the same nadi. Traditionally given high weight; some schools "
                     "waive it in certain nakshatra/sign combinations.")
    if bad_bhakoot:
        notes.append("Bhakoot dosha: the Moon signs fall in a 2/12, 5/9 or 6/8 relationship.")
    return {
        "total": total, "max": 36, "verdict": _verdict(total), "kootas": kootas,
        "groom": {"name": groom["meta"].get("name") or "Groom", "moon_sign": g["sign"], "nakshatra": g["nak"],
                  "pada": g["pada"], "manglik": mg},
        "bride": {"name": bride["meta"].get("name") or "Bride", "moon_sign": b["sign"], "nakshatra": b["nak"],
                  "pada": b["pada"], "manglik": mb},
        "manglik_note": mnote, "notes": notes,
        "disclaimer": "Ashtakoota is one traditional lens. A full match also compares the 7th house, "
                      "dashas and overall chart strength. Schools differ on some tables.",
    }
