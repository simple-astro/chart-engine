"""KP horary (Prashna): the querent thinks of the question and gives a number from 1 to 249.

The number fixes the ascendant at the start of the matching KP sub (the 243 nakshatra subs,
split where they cross a sign boundary, give 249 divisions). Cusps are cast for that ascendant
at the place of the question; planets are taken at the moment of the question. The answer
comes from the sub-lord of the cusp that governs the matter: if it signifies the houses that
fulfil the matter, the answer tends to yes; if it signifies the houses that deny it, no.
"""
from __future__ import annotations

from datetime import datetime

import swisseph as swe

from core import constants as C
from core import ephemeris
from core.grahas import compute_grahas
from core.houses import _make_cusp, Houses
from core.kp import kp_lords, planet_significators
from core.ephemeris import set_sidereal_mode


def _build_249() -> list[float]:
    starts, lon = [], 0.0
    for nak in range(27):
        lord = C.NAKSHATRA_LORDS[nak]
        order = C.VIMSOTTARI_ORDER
        i = order.index(lord)
        for k in range(9):
            sub = order[(i + k) % 9]
            length = C.VIMSOTTARI_YEARS[sub] / C.VIMSOTTARI_TOTAL_YEARS * C.NAKSHATRA_ARC
            starts.append(lon)
            boundary = (int(lon // 30) + 1) * 30.0
            if lon + 1e-9 < boundary < lon + length - 1e-9:
                starts.append(boundary)  # the sub crosses into the next sign: two horary numbers
            lon += length
    return starts


KP_249 = _build_249()
assert len(KP_249) == 249

# question type: primary house, houses that fulfil it, houses that deny it
QUESTIONS = {
    "marriage": ("Marriage", 7, {2, 7, 11}, {1, 6, 10}),
    "love": ("Love or relationship", 5, {5, 7, 11}, {1, 6, 10, 12}),
    "job": ("Getting a job or promotion", 10, {2, 6, 10, 11}, {1, 5, 9, 12}),
    "business": ("Business or money gain", 11, {2, 6, 10, 11}, {5, 8, 12}),
    "travel": ("Foreign travel or settling abroad", 12, {3, 9, 12}, {2, 4, 11}),
    "property": ("Buying property or a vehicle", 4, {4, 11, 12}, {3, 5, 10}),
    "health": ("Recovery from illness", 1, {1, 5, 11}, {6, 8, 12}),
    "exam": ("Passing an exam or admission", 4, {4, 9, 11}, {3, 8, 10}),
    "child": ("Having a child", 5, {2, 5, 11}, {1, 4, 10}),
    "lawsuit": ("Winning a dispute or court case", 6, {1, 6, 11}, {5, 8, 12}),
    "lost": ("Finding something lost", 11, {2, 6, 11}, {5, 8, 12}),
}
HOUSE_WORDS = {1: "yourself", 2: "family and money", 3: "effort and short journeys", 4: "home and property",
               5: "love, children and studies", 6: "work, service and winning over rivals", 7: "partnership",
               8: "obstacles and delays", 9: "luck and long journeys", 10: "career and status",
               11: "gains and fulfilment of wishes", 12: "losses, expenses and foreign lands"}
WEEKDAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Sunday first


def number_point(n: int) -> dict:
    lon = KP_249[n - 1] + 1e-7
    lords = kp_lords(lon)
    return {"number": n, "longitude": round(KP_249[n - 1], 4), "sign": C.SIGNS[int(lon // 30)],
            "nakshatra": C.NAKSHATRAS[int(lon // C.NAKSHATRA_ARC)], "sign_lord": lords.sign_lord,
            "star_lord": lords.star_lord, "sub_lord": lords.sub_lord}


def _houses_at(jd: float, lat: float, lon: float) -> tuple[float, tuple]:
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    return ascmc[0] % 360.0, cusps


def horary_houses(target_asc: float, jd_now: float, lat: float, lon: float, ayanamsha: str = "krishnamurti") -> Houses:
    """Placidus cusps for the moment (within the next sidereal day) when the ascendant reaches target_asc."""
    set_sidereal_mode(ayanamsha)
    asc0, _ = _houses_at(jd_now, lat, lon)
    want = (target_asc - asc0) % 360.0
    lo, hi = 0.0, 0.99727
    for _ in range(50):  # ascendant progress over a sidereal day is monotonic: bisect it
        mid = (lo + hi) / 2
        got = (_houses_at(jd_now + mid, lat, lon)[0] - asc0) % 360.0
        lo, hi = (mid, hi) if got < want else (lo, mid)
    asc, cusps = _houses_at(jd_now + lo, lat, lon)
    _, ascmc = swe.houses_ex(jd_now + lo, lat, lon, b"P", swe.FLG_SIDEREAL)
    return Houses(ascendant=asc, midheaven=ascmc[1] % 360.0, house_system="placidus",
                  cusps=[_make_cusp(i + 1, cusps[i]) for i in range(12)])


def judge(n: int, kind: str, when: datetime, lat: float, lon: float, ayanamsha: str = "krishnamurti") -> dict:
    if not 1 <= n <= 249:
        raise ValueError("number must be from 1 to 249")
    if kind not in QUESTIONS:
        raise ValueError(f"unknown question type: {kind}")
    title, primary, good, bad = QUESTIONS[kind]
    jd = ephemeris.julian_day(when)
    point = number_point(n)
    houses = horary_houses(point["longitude"] + 1e-7, jd, lat, lon, ayanamsha)
    grahas = compute_grahas(jd, ayanamsha)
    sig = planet_significators(grahas, houses)

    cusp = houses.cusps[primary - 1]
    csl = kp_lords(cusp.longitude).sub_lord
    s = set(sig[csl]["houses"])
    yes, no = sorted(s & good), sorted(s & bad)
    score = len(yes) - len(no) + (1 if primary in s else 0)
    if yes and score >= 2 and not no:
        verdict, label = "yes", "Yes"
    elif yes and score > 0:
        verdict, label = "likely", "Likely yes"
    elif yes:
        verdict, label = "mixed", "Possible, with delays"
    else:
        verdict, label = "no", "Unlikely for now"

    moon_lords = kp_lords(grahas["Moon"].longitude)
    asc_lords = kp_lords(houses.ascendant)
    weekday = WEEKDAY_LORD[(when.weekday() + 1) % 7]
    ruling = list(dict.fromkeys([asc_lords.star_lord, asc_lords.sign_lord, moon_lords.star_lord,
                                 moon_lords.sign_lord, weekday]))
    moon_sig = set(sig["Moon"]["houses"])

    reasons = [f"Your number {n} places the rising point in {point['sign']}, {point['nakshatra']} nakshatra.",
               f"For this question Jyotish looks at your {primary}{_ord(primary)} house ({HOUSE_WORDS[primary]}). "
               f"Its deciding planet (cusp sub-lord) is {csl}."]
    if yes:
        reasons.append(f"{csl} connects to " + _list([f"{h}{_ord(h)} ({HOUSE_WORDS[h]})" for h in yes]) + " — houses that support this.")
    if no:
        reasons.append(("It also touches " if yes else f"{csl} connects to ") + _list([f"{h}{_ord(h)} ({HOUSE_WORDS[h]})" for h in no]) + " — houses that hold it back.")
    if not yes:
        reasons.append(f"{csl} does not connect to the houses that bring this about right now.")
    if csl in ruling and verdict != "no":
        reasons.append(f"{csl} is also one of the ruling planets of this moment, which strengthens the answer.")
    if moon_sig & good and verdict != "no":
        reasons.append("Your Moon — your mind at the time of asking — supports the matter too.")

    return {"number": point, "question": {"kind": kind, "title": title, "house": primary},
            "asked_at": when.isoformat(), "cusp_sub_lord": csl, "signifies": sorted(s),
            "supports": yes, "denies": no, "verdict": verdict, "label": label,
            "ruling_planets": ruling, "ascendant": round(houses.ascendant, 4), "reasons": reasons}


def _ord(n: int) -> str:
    return "th" if 10 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _list(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
