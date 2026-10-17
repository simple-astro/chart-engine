"""Jamakkol Prashna: the Tamil horary cast for the moment and place a question is asked.

Three points and eight "jama" planets are worked out from the clock, the Sun and the day:

- Udayam (the rising point of the question): starts at the Sun's degree at sunrise and moves forward through all
  twelve signs between sunrise and sunset, each sign taking a twelfth of the daylight. At night the same again, from
  the Sun's degree at sunset to the next sunrise (checked against jamakkolprasannam.com's chart at 00:15 IST).
- Arudam (the intention behind the question): from the minute hand only. Each 5 minutes is one sign from Aries.
- Kavippu (the hidden obstacle, also called Chatra): the Sun's sign gives a veedhi (Taurus, Aries or Gemini). Count
  from the Arudam to the veedhi, and the same count from the Udayam gives the Kavippu's sign; its degree mirrors the
  Arudam's (30° minus the Arudam's degree), as three Jamakkol programs show. It moves backwards: the first planet
  below it is the one it is "catching".
- Jama planets (the outer planets): Sun, Mars, Jupiter, Mercury, Venus, Saturn, Moon and Paambu (the snake), 45°
  apart in that order. They turn backwards through the zodiac at 45° per jamam of 1½ hours. At 6:00 on the clock
  the weekday's lord stands at the very end of Pisces. Each is in the sign of its degree.
- Maandi: the Sun's degree now, plus 12°, plus 24° for each part of the day (or night) before Gulika's part
  (by day Saturday is the 1st part … Sunday the 7th; by night Tuesday the 1st … Wednesday the 7th), plus 180° at
  night. Matches jamakkolprasannam.com to 0.01° (it uses Lahiri; ours is KP, about 0.1° apart). Shown as a point
  to take care around, never read for death.
The transit planets (the inner planets) are the real sky at that moment; they decide strength. The reading rules
below are deterministic: they never invent a fact, and the AI only explains what they found.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from core import constants as C
from core.dignity import dignity
from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.panchang import _sidereal_sun_moon, compute_panchang

JAMA = ["Sun", "Mars", "Jupiter", "Mercury", "Venus", "Saturn", "Moon", "Paambu"]
WEEKDAY_LORD = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]  # Python weekday 0 = Monday
JAMAM_MINUTES = 90
AYANAMSHA = "krishnamurti"

# The Sun's sign gives the veedhi used for Kavippu.
VEEDHI = {11: 1, 0: 1, 5: 1, 6: 1, 1: 0, 2: 0, 3: 0, 4: 0, 7: 2, 8: 2, 9: 2, 10: 2}
SIRSHODAYA, PRISHTODAYA = {2, 4, 5, 6, 7, 10}, {0, 1, 3, 8, 9}  # Pisces rises both ways
SUBHA_UDAYAM = {4, 5, 6, 7, 8, 9}        # Leo to Capricorn: the Sun's half
SUBHA_ARUDAM = {10, 11, 0, 1, 2, 3}      # Aquarius to Cancer: the Moon's half
# Planets in the Udayam by how they rise: head first (success), back first (failure), both ways (delay).
PLANET_RISE = {"Mercury": "head", "Jupiter": "head", "Venus": "head", "Rahu": "head", "Paambu": "head",
               "Sun": "back", "Mars": "back", "Saturn": "back", "Moon": "both", "Ketu": "both"}
GULIKA_PART_DAY = {0: 7, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}    # Vedic weekday (Sunday = 0) -> part of the day
GULIKA_PART_NIGHT = {0: 3, 1: 2, 2: 1, 3: 7, 4: 6, 5: 5, 6: 4}
MOOLATRIKONA = {"Sun": 4, "Moon": 1, "Mars": 0, "Mercury": 5, "Jupiter": 8, "Venus": 6, "Saturn": 10}
STRENGTH = {"exalted": 4, "moolatrikona": 3, "own": 2, "debilitated": 0}  # anything else 1
CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
DAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Vedic weekday, Sunday = 0
TAMIL_MONTH = ["Chithirai", "Vaikasi", "Aani", "Aadi", "Aavani", "Purattasi", "Aippasi", "Karthigai", "Margazhi",
               "Thai", "Maasi", "Panguni"]  # by the Sun's sidereal sign, Aries first

# What a planet near the Udayam points the question to (gentle, everyday significations).
ABOUT = {
    "Sun": "father, government, status or a promotion",
    "Moon": "mother, home, food, travel or a quick change",
    "Mars": "land, property, a brother or a dispute",
    "Mercury": "studies, a match or an agreement, writing or trade",
    "Jupiter": "children, money, gold, teaching or higher studies",
    "Venus": "a partner or spouse, money, comforts or a vehicle",
    "Saturn": "work and a job, service or something slow and long",
    "Paambu": "foreign travel, a pregnancy or something sudden or unusual",
    "Rahu": "foreign travel or something unusual",
    "Ketu": "letting go, legal matters or spiritual questions",
}
HOUSE_ABOUT = {
    1: "yourself", 2: "money and family", 3: "a sibling, courage or a message", 4: "home, mother, property or studies",
    5: "children, love or learning", 6: "work under someone, health or a dispute", 7: "marriage or a partnership",
    8: "a sudden change", 9: "father, long travel or blessings", 10: "career and reputation",
    11: "gains, profit or an elder sibling", 12: "expenses, a move or going abroad",
}

# Questions offered (sensitive matters such as survival, separation or someone else's guilt are not judged).
QUESTIONS = {
    "career": ("A job or career", [10], ["Saturn"]),
    "business": ("Business or self-employment", [10, 7], ["Mercury"]),
    "money": ("Money or a deal", [2, 11], ["Jupiter", "Venus"]),
    "marriage": ("Marriage or a match", [7], ["Venus", "Mercury"]),
    "children": ("Children", [5], ["Jupiter"]),
    "property": ("Land, a house or a vehicle", [4], ["Mars", "Venus"]),
    "education": ("Studies or exams", [4, 5], ["Mercury"]),
    "travel": ("Travel or going abroad", [9, 12], ["Paambu"]),
    "dispute": ("A dispute or court case", [6, 7], ["Jupiter"]),
    "general": ("Something else", [], []),
}


def _sign(lon: float) -> int:
    return int(lon % 360 // 30)


def _house(from_sign: int, sign: int) -> int:
    return (sign - from_sign) % 12 + 1


def _point(lon: float) -> dict:
    lon %= 360
    return {"lon": round(lon, 4), "sign_index": _sign(lon), "sign": C.SIGNS[_sign(lon)], "deg": round(lon % 30, 4),
            "star": C.NAKSHATRAS[int(lon // C.NAKSHATRA_ARC) % 27]}


def _day_bounds(when: datetime, lat: float, lon: float, tz: str) -> tuple[str, datetime, datetime, float]:
    """("day"|"night", start, end, the Sun's sidereal degree at the start) for the moment ``when``."""
    local = when.astimezone(ZoneInfo(tz)).date()
    today = compute_panchang(local, lat, lon, tz)
    if today.sunrise <= when < today.sunset:
        return "day", today.sunrise, today.sunset, _sidereal_sun_moon(julian_day(today.sunrise))[0]
    if when >= today.sunset:
        start, end = today.sunset, compute_panchang(local + timedelta(days=1), lat, lon, tz).sunrise
    else:
        start, end = compute_panchang(local - timedelta(days=1), lat, lon, tz).sunset, today.sunrise
    return "night", start, end, _sidereal_sun_moon(julian_day(start))[0]


def jama_positions(when: datetime, tz: str) -> dict:
    """The eight jama planets, the jamam (1–16 from 6:00 on the clock) and its ruler."""
    local = when.astimezone(ZoneInfo(tz))
    day = (local - timedelta(hours=6)).date()  # the jama day runs 6:00 to 6:00
    six = datetime.combine(day, time(6, 0), tzinfo=ZoneInfo(tz))
    minutes = (local - six).total_seconds() / 60
    lord = WEEKDAY_LORD[day.weekday()]
    li = JAMA.index(lord)
    planets = {p: _point(360 - minutes * 45 / JAMAM_MINUTES + (li - i) * 45) for i, p in enumerate(JAMA)}
    n = int(minutes // JAMAM_MINUTES) + 1
    start = six + timedelta(minutes=(n - 1) * JAMAM_MINUTES)
    timeline = [{"n": k + 1, "ruler": JAMA[(li - k) % 8],
                 "start": (six + timedelta(minutes=k * JAMAM_MINUTES)).strftime("%H:%M"),
                 "end": (six + timedelta(minutes=(k + 1) * JAMAM_MINUTES)).strftime("%H:%M")} for k in range(16)]
    return {"weekday": day.strftime("%A"), "lord": lord, "number": n, "ruler": JAMA[(li - (n - 1)) % 8],
            "timeline": timeline,
            "start": start.isoformat(), "end": (start + timedelta(minutes=JAMAM_MINUTES)).isoformat(),
            "planets": planets}


def cast(when: datetime, lat: float, lon: float, tz: str) -> dict:
    """The Jamakkol chart for a question asked at ``when`` (timezone-aware) at this place."""
    if when.tzinfo is None:
        raise ValueError("the time needs a timezone")
    period, start, end, start_deg = _day_bounds(when, lat, lon, tz)
    frac = (when - start).total_seconds() / (end - start).total_seconds()
    udayam = _point(start_deg + 360 * frac)
    local = when.astimezone(ZoneInfo(tz))
    m = local.minute + local.second / 60
    arudam = _point((m // 5) * 30 + (m % 5) / 5 * 30)
    grahas = compute_grahas(julian_day(when), AYANAMSHA)
    sun_sign = grahas["Sun"].sign_index
    veedhi = VEEDHI[sun_sign]
    kav_sign = (udayam["sign_index"] + (veedhi - arudam["sign_index"]) % 12) % 12
    count = (veedhi - arudam["sign_index"]) % 12 + 1
    kavippu = {**_point(kav_sign * 30 + min(30 - arudam["deg"], 29.9999)), "veedhi": C.SIGNS[veedhi],
               "count": count, "sun_sign": C.SIGNS[sun_sign], "tamil_month": TAMIL_MONTH[sun_sign]}
    transit = {n: {**_point(g.longitude), "retrograde": g.retrograde, "dignity": dignity(n, g.sign_index)}
               for n, g in grahas.items()}
    hora_i = min(11, int(frac * 12)) + (12 if period == "night" else 0)
    vedic_wd = (start.astimezone(ZoneInfo(tz)).weekday() + 1) % 7  # the day (or night) began at this sunrise/sunset
    part = (GULIKA_PART_DAY if period == "day" else GULIKA_PART_NIGHT)[vedic_wd]
    maandi = _point(grahas["Sun"].longitude + (180 if period == "night" else 0) + 12 + 24 * (part - 1))
    hora = CHALDEAN[(CHALDEAN.index(DAY_LORD[vedic_wd]) + hora_i) % 7]
    return {"asked_at": when.isoformat(), "place": {"lat": lat, "lon": lon, "tz_name": tz}, "period": period,
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "udayam": udayam, "arudam": arudam, "kavippu": kavippu, "maandi": maandi, "jama": jama_positions(when, tz),
            "transit": transit, "hora": hora, "vedic_weekday":
            ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][vedic_wd]}


def _exchanges(a_signs: dict, b_signs: dict, same: bool) -> list[str]:
    """Parivarthana: planet a sits in b's sign while b sits in a's (a from one set, b from the other)."""
    out = []
    for a, sa in a_signs.items():
        for b, sb in b_signs.items():
            if a == b or (same and a > b):
                continue
            if C.SIGN_LORDS[sa] == b and C.SIGN_LORDS[sb] == a:
                out.append(f"{a}–{b}")
    return out


def confirmation(chart: dict) -> list[list[str]]:
    """The Prashna confirmation checklist (as Jamakkol programs list it): what touches the Udayam, the houses of the
    Arudam and Kavippu, strong and weak planets in both layers, the 10th lord, exchanges, what the Kavippu catches."""
    U, A, K = chart["udayam"], chart["arudam"], chart["kavippu"]
    jama, sky = chart["jama"]["planets"], chart["transit"]
    seven = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    ahead = {p: (x["lon"] - U["lon"]) % 360 for p, x in jama.items()}
    dig = lambda p, si: dignity(p, si)
    names = lambda xs: ", ".join(xs) if xs else "–"
    tl = C.SIGN_LORDS[(U["sign_index"] + 9) % 12]
    pts = {**{f"{p} (jama)": x["lon"] for p, x in jama.items()}, **{p: x["lon"] for p, x in sky.items()}}
    behind = {n: (K["lon"] - lon) % 360 for n, lon in pts.items() if (K["lon"] - lon) % 360 > 1e-6}
    js = {p: x["sign_index"] for p, x in jama.items() if p in seven}
    ss = {p: sky[p]["sign_index"] for p in seven}
    return [
        ["Jama planet that crossed the Udayam", max(ahead, key=ahead.get)],
        ["Jama planet approaching the Udayam", min(ahead, key=ahead.get)],
        ["Sky planets in the Udayam", names([p for p, x in sky.items() if x["sign_index"] == U["sign_index"]])],
        ["Jama planets in the Udayam", names([p for p, x in jama.items() if x["sign_index"] == U["sign_index"]])],
        ["Udayam to Arudam (house)", str(_house(U["sign_index"], A["sign_index"]))],
        ["Udayam to Kavippu (house)", str(_house(U["sign_index"], K["sign_index"]))],
        ["Exalted sky planets", names([p for p in sky if sky[p]["dignity"] == "exalted"])],
        ["Exalted jama planets", names([p for p in seven if dig(p, jama[p]["sign_index"]) == "exalted"])],
        ["Debilitated sky planets", names([p for p in sky if sky[p]["dignity"] == "debilitated"])],
        ["Debilitated jama planets", names([p for p in seven if dig(p, jama[p]["sign_index"]) == "debilitated"])],
        ["Same sign, sky and jama", names([p for p in seven if jama[p]["sign_index"] == sky[p]["sign_index"]]
                                          + (["Paambu"] if jama["Paambu"]["sign_index"] == sky["Rahu"]["sign_index"] else []))],
        ["10th lord from the Udayam", f"{tl}: sky in house {_house(U['sign_index'], sky[tl]['sign_index'])}, "
                                      f"jama in house {_house(U['sign_index'], jama[tl]['sign_index'])}"],
        ["Exchanges among sky planets", names(_exchanges(ss, ss, True))],
        ["Exchanges among jama planets", names(_exchanges(js, js, True))],
        ["Exchanges, sky with jama", names(_exchanges(ss, js, False))],
        ["Kavippu is catching", min(behind, key=behind.get) if behind else "–"],
        ["Maandi from the Udayam (house)", str(_house(U["sign_index"], chart["maandi"]["sign_index"]))],
        ["Hora", chart["hora"]],
    ]


def _power(planet: str, transit: dict) -> tuple[int, str]:
    """Strength score of a sign lord in the sky: exalted 4, moolatrikona 3, own 2, debilitated 0, otherwise 1."""
    x = transit[planet]
    d = "moolatrikona" if MOOLATRIKONA.get(planet) == x["sign_index"] and x["dignity"] != "exalted" else x["dignity"]
    return STRENGTH.get(d, 1), d


def _strength(planet: str, transit: dict) -> str:
    """The inner (transit) planet decides strength; Paambu follows Rahu."""
    return transit["Rahu" if planet == "Paambu" else planet]["dignity"]


def read(chart: dict, kind: str) -> dict:
    """Rule-based reading of a Jamakkol chart for one kind of question."""
    if kind not in QUESTIONS:
        raise ValueError(f"unknown question kind: {kind}")
    title, houses, karakas = QUESTIONS[kind]
    U, A, K = chart["udayam"]["sign_index"], chart["arudam"]["sign_index"], chart["kavippu"]["sign_index"]
    jama, transit = chart["jama"]["planets"], chart["transit"]
    a_house, k_house = _house(U, A), _house(U, K)
    lord = C.SIGN_LORDS[U]
    in_udayam = [p for p, x in jama.items() if x["sign_index"] == U] + \
                [p for p, x in transit.items() if x["sign_index"] == U]
    ahead = {p: (x["lon"] - chart["udayam"]["lon"]) % 360 for p, x in jama.items()}
    approaching = min(ahead, key=ahead.get)
    crossed = max(ahead, key=ahead.get)  # the one just behind (largest gap ahead = smallest gap behind)
    in_kavippu = list(dict.fromkeys([p for p, x in jama.items() if x["sign_index"] == K] +
                                    [p for p, x in transit.items() if x["sign_index"] == K]))
    pos, neg, block = [], [], []

    if kind == "general":
        houses = [a_house]
        about = f"Your question looks to be about {HOUSE_ABOUT[a_house]} (the Arudam is {a_house} from the Udayam)."
    else:
        about = f"Your question: {title.lower()}."
    for h in houses:
        if k_house == h:
            block.append(f"The Kavippu (hidden obstacle) falls in house {h} from the Udayam, the house of this matter.")
    for p in karakas:
        if p in in_kavippu:
            block.append(f"{p}, the significator of this matter, sits with the Kavippu.")
        if _strength(p, transit) == "debilitated":
            neg.append(f"{p}, the significator, is weak (debilitated) in the sky now.")
        elif _strength(p, transit) in ("exalted", "own"):
            pos.append(f"{p}, the significator, is strong ({_strength(p, transit)}) in the sky now.")
    if k_house == 1:
        block.append("The Kavippu sits on the Udayam: the timing for you yourself is weak right now.")
    if a_house in (6, 8, 12):
        neg.append(f"The Arudam is {a_house} from the Udayam (veda): it may not happen, or not feel satisfying.")
    elif a_house in (3, 11):
        pos.append(f"The Arudam is {a_house} from the Udayam: a sign of success.")
    if k_house in (2, 11):
        neg.append(f"The Kavippu is {k_house} from the Udayam: expect obstacles along the way.")
    ld = transit[lord]
    if ld["dignity"] == "debilitated":
        neg.append(f"The Udayam lord {lord} is weak (debilitated).")
    elif ld["dignity"] == "exalted":
        pos.append(f"The Udayam lord {lord} is exalted.")
    if ld["retrograde"]:
        neg.append(f"The Udayam lord {lord} is retrograde: effort may not convert easily.")
    if _house(U, ld["sign_index"]) in (10, 11):
        pos.append(f"The Udayam lord {lord} is in house {_house(U, ld['sign_index'])} from the Udayam: success.")
    eleventh = C.SIGN_LORDS[(U + 10) % 12]
    if approaching == eleventh:
        pos.append(f"{eleventh}, lord of the 11th (gains), is approaching the Udayam.")
    if approaching == "Moon":
        pos.append("The Moon is approaching the Udayam: things can move quickly.")
    if approaching in ("Saturn", "Paambu"):
        neg.append(f"{'Saturn' if approaching == 'Saturn' else 'Paambu'} is approaching the Udayam: it will take time.")

    rise = {PLANET_RISE[p] for p in in_udayam}  # planets in the Udayam: how they rise decides
    names = lambda kind_: ", ".join(dict.fromkeys(p for p in in_udayam if PLANET_RISE[p] == kind_))
    if "head" in rise:
        pos.append(f"{names('head')} in the Udayam rise{'s' if ',' not in names('head') else ''} head first: success.")
    if "back" in rise:
        neg.append(f"{names('back')} in the Udayam rise{'s' if ',' not in names('back') else ''} back first: hard going.")
    if "both" in rise:
        neg.append(f"{names('both')} in the Udayam rise{'s' if ',' not in names('both') else ''} both ways: "
                   "success after a delay.")

    if not in_udayam:  # these signs count only when the Udayam is empty
        if U in SIRSHODAYA:
            pos.append("The Udayam rises head first (sirshodaya): success.")
        elif U in PRISHTODAYA:
            neg.append("The Udayam rises back first (prishtodaya): hard going.")
        else:
            neg.append("The Udayam rises both ways (Pisces): success after a delay.")
        sun = transit["Sun"]["sign_index"]
        rel = (U - sun) % 12
        if rel % 3 == 0:
            neg.append("The Udayam faces downward (adhomukha) from the Sun: hard going.")
        elif rel % 3 == 2:
            pos.append("The Udayam faces upward (urdhvamukha) from the Sun: success.")
        if U in SUBHA_UDAYAM and A in SUBHA_ARUDAM:
            pos.append("Both the Udayam and the Arudam fall in auspicious halves.")
        elif U not in SUBHA_UDAYAM and A not in SUBHA_ARUDAM:
            neg.append("Both the Udayam and the Arudam fall in inauspicious halves.")

    M = chart["maandi"]["sign_index"]
    if M == U:
        neg.append("Maandi sits on the Udayam: take extra care, and expect delays.")
    elif _house(U, M) in houses:
        neg.append(f"Maandi sits in house {_house(U, M)} from the Udayam, the house of this matter: take care, "
                   "and expect delays.")

    score = len(pos) - len(neg)
    if block:
        verdict, label = "no", "Not favourable now"
    elif score >= 2:
        verdict, label = "yes", "Favourable"
    elif score >= 1:
        verdict, label = "likely", "Likely, with effort"
    elif score >= 0:
        verdict, label = "mixed", "Mixed: success after a delay"
    else:
        verdict, label = "no", "Unlikely for now"

    timing = None
    moon = jama["Moon"]["sign_index"]
    rays = {"exalted": 63, "debilitated": 0}.get(transit["Moon"]["dignity"], 21)
    if verdict in ("yes", "likely") and rays:
        count = (moon - U) % 12 + 1
        timing = {"days": rays * count, "text": f"Roughly {rays * count} days: the Moon's rays ({rays}) × {count} signs "
                                                 "from the jama Moon to the Udayam. Treat it as a window, not a date."}
    # The 10th from the Udayam (ucchiyal sindanai): where its lord sits confirms what the question is about.
    tenth = (U + 9) % 12
    tlord = C.SIGN_LORDS[tenth]
    th = _house(U, transit[tlord]["sign_index"])
    in_tenth = list(dict.fromkeys([p for p, x in jama.items() if x["sign_index"] == tenth] +
                                  [p for p, x in transit.items() if x["sign_index"] == tenth]))
    confirm = [f"The 10th lord {tlord} sits in house {th} from the Udayam: the question is tied to {HOUSE_ABOUT[th]}."]
    if in_tenth:
        confirm.append(f"In the 10th from the Udayam: {', '.join(in_tenth)}, which confirms the topic.")
    # The Kavippu in general: the area of life it holds back, and the planets whose matters it blocks.
    kav_notes = [f"The Kavippu is in house {k_house} from the Udayam: {HOUSE_ABOUT[k_house]} may meet hidden obstacles."]
    kav_notes += [f"{p} is with the Kavippu: its matters ({ABOUT[p]}) are held back for now." for p in in_kavippu]
    # Exalted and weak planets in the sky: their matters prosper or struggle (the Kavippu still has the last word).
    strengths = []
    for p, x in transit.items():
        if x["dignity"] in ("exalted", "debilitated"):
            good = x["dignity"] == "exalted"
            strengths.append(f"{p} is {'exalted' if good else 'weak (debilitated)'}: {ABOUT[p]} "
                             f"{'prosper' if good else 'struggle'}" + (" (but it is with the Kavippu)" if good and p in in_kavippu else "") + ".")
    # Double confirmation: a planet that matters here whose jama and sky positions share a sign.
    matters = set(karakas) | set(in_udayam) | set(in_kavippu) | {approaching}
    doubled = [p for p in JAMA if p != "Paambu" and p in matters and jama[p]["sign_index"] == transit[p]["sign_index"]]
    if jama["Paambu"]["sign_index"] == transit["Rahu"]["sign_index"] and ({"Paambu", "Rahu"} & matters):
        doubled.append("Paambu")
    confirm += [f"{p} is doubled (its jama and sky positions share {C.SIGNS[jama[p]['sign_index']]}): its signal "
                "here is confirmed." for p in doubled]
    # Arudam lord against Kavippu lord (shown for the astrologer's judgement; it does not change the answer).
    al, kl = C.SIGN_LORDS[A], C.SIGN_LORDS[K]
    (ap, ad), (kp, kd) = _power(al, transit), _power(kl, transit)
    side = ("the hidden side (Kavippu) is stronger" if kp > ap else "the intention (Arudam) is stronger" if ap > kp
            else "they are evenly matched")
    lords = {"arudam_lord": al, "arudam_power": ap, "arudam_dignity": ad, "kavippu_lord": kl, "kavippu_power": kp,
             "kavippu_dignity": kd,
             "text": f"Arudam lord {al} ({ad}, {ap}) against Kavippu lord {kl} ({kd}, {kp}): {side}."}
    return {
        "question": {"kind": kind, "title": title, "houses": houses, "karakas": karakas},
        "confirm": confirm, "kavippu_notes": kav_notes, "strengths": strengths, "lords": lords, "doubled": doubled,
        "maandi_house": _house(U, M),
        "verdict": verdict, "label": label, "about": about,
        "focus": [f"{p} is in the Udayam: the question touches {ABOUT[p]}." for p in dict.fromkeys(in_udayam)][:3]
                 or [f"The Udayam is empty: no urgency; the Udayam lord {lord} shows the matter."],
        "approaching": {"planet": approaching, "about": ABOUT[approaching]},
        "crossed": {"planet": crossed, "about": ABOUT[crossed]},
        "arudam_house": a_house, "kavippu_house": k_house, "in_kavippu": in_kavippu,
        "obstacles": block, "for": pos, "against": neg, "timing": timing,
    }


def jamakkol(kind: str, when: datetime, lat: float, lon: float, tz: str) -> dict:
    chart = cast(when, lat, lon, tz)
    return {**chart, "confirmation": confirmation(chart), "reading": read(chart, kind)}


def kinds() -> list[dict]:
    return [{"kind": k, "title": v[0]} for k, v in QUESTIONS.items()]
