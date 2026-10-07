"""Daily muhurat: how suitable a day is for common undertakings.

Classical panchang rules (tithi, weekday, nakshatra, yoga, karana) give the day's
general quality for each activity; when the native's Moon is known, Tara bala
(birth star to day star) and Chandra bala (natal Moon to day Moon) personalise it.
Time windows come from sunrise/sunset: Abhijit muhurat, day Choghadiya and the
Rahu kalam / Yamaganda periods to avoid. Traditional guidance, not a certainty.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from core import constants as C
from core.panchang import compute_panchang

SUN, MON, TUE, WED, THU, FRI, SAT = range(7)

# Nakshatra groups by index (0 = Ashwini ... 26 = Revati).
DHRUVA = {3, 11, 20, 25}          # fixed: foundations, homes, long-term
CHARA = {6, 14, 21, 22, 23}       # movable: travel, vehicles
KSHIPRA = {0, 7, 12}              # swift: trade, learning, buying, travel
MRIDU = {4, 13, 16, 26}           # soft: marriage, arts, jewellery, friendship
MISHRA = {2, 15}
UGRA = {1, 9, 10, 19, 24}         # fierce
TIKSHNA = {5, 8, 17, 18}          # sharp

RIKTA = {4, 9, 14}                # 4th, 9th, 14th tithi of either paksha
BAD_YOGAS = {1, 6, 9, 10, 13, 15, 17, 19, 27}  # Vishkambha, Atiganda, Shula, Ganda, Vyaghata, Vajra, Vyatipata, Parigha, Vaidhriti

ACTIVITIES = [
    {"key": "travel", "name": "Travel", "icon": "plane",
     "naks": {0, 4, 6, 7, 12, 16, 21, 22, 26}, "good_days": {MON, WED, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "start", "name": "New work or business", "icon": "rocket",
     "naks": KSHIPRA | DHRUVA | MRIDU | {6, 21}, "good_days": {WED, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "property", "name": "Property or land", "icon": "home",
     "naks": DHRUVA | MRIDU | {6, 7}, "good_days": {MON, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "vehicle", "name": "Buying a vehicle", "icon": "car",
     "naks": CHARA | KSHIPRA | MRIDU, "good_days": {MON, WED, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "gold", "name": "Gold, jewellery & clothes", "icon": "gem",
     "naks": MRIDU | KSHIPRA | {3, 11, 20, 25}, "good_days": {WED, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "marriage", "name": "Marriage or engagement", "icon": "rings",
     "naks": {3, 4, 9, 11, 12, 14, 16, 18, 20, 25, 26}, "good_days": {MON, WED, THU, FRI},
     "bad_days": {TUE, SAT, SUN}, "shukla": True},
    {"key": "griha", "name": "Griha pravesh (housewarming)", "icon": "door",
     "naks": DHRUVA | MRIDU | {22, 23}, "good_days": {MON, WED, THU, FRI}, "bad_days": {TUE, SUN}, "shukla": True},
    {"key": "study", "name": "Studies or a new course", "icon": "book",
     "naks": KSHIPRA | MRIDU | CHARA | {6}, "good_days": {SUN, WED, THU, FRI}, "bad_days": {TUE, SAT}},
    {"key": "meeting", "name": "Interview or key meeting", "icon": "handshake",
     "naks": KSHIPRA | MRIDU | DHRUVA, "good_days": {SUN, WED, THU}, "bad_days": {TUE, SAT}},
]

TARAS = [("Janma", 0, "your birth star — fine for routine, not ideal for big beginnings"),
         ("Sampat", 1, "wealth — supportive"), ("Vipat", -1, "obstacles — be careful"),
         ("Kshema", 1, "well-being — supportive"), ("Pratyak", -1, "opposition — expect resistance"),
         ("Sadhana", 1, "achievement — supportive"), ("Naidhana", -2, "the most difficult star — avoid big starts"),
         ("Mitra", 1, "friendly — supportive"), ("Param Mitra", 1, "very friendly — supportive")]
CHANDRA_GOOD, CHANDRA_BAD = {1, 3, 6, 7, 10, 11}, {4, 8, 12}

# Day Choghadiya: 8 equal parts from sunrise, starting with the weekday's lord.
CHOG_ORDER = ["Udveg", "Chal", "Labh", "Amrit", "Kaal", "Shubh", "Rog"]
CHOG_START = {SUN: "Udveg", MON: "Amrit", TUE: "Rog", WED: "Labh", THU: "Shubh", FRI: "Chal", SAT: "Kaal"}
CHOG_QUALITY = {"Amrit": "best", "Shubh": "good", "Labh": "good", "Chal": "neutral",
                "Udveg": "avoid", "Kaal": "avoid", "Rog": "avoid"}
DISHA_SHOOL = {SUN: "west", MON: "east", TUE: "north", WED: "north", THU: "south", FRI: "west", SAT: "east"}

VERDICTS = [(3, "excellent", "Very good"), (1, "good", "Good"), (-1, "fair", "Okay with care"),
            (-99, "avoid", "Better to avoid")]


def _verdict(score: int) -> tuple[str, str]:
    return next((k, label) for floor, k, label in VERDICTS if score >= floor)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def day_factors(p, birth_nak: int | None, birth_moon_sign: int | None) -> dict:
    wd = C.WEEKDAY_NAMES.index(p.weekday)
    tara = chandra = None
    if birth_nak is not None:
        n = (p.nakshatra_index - birth_nak) % 27 % 9
        name, score, note = TARAS[n]
        tara = {"number": n + 1, "name": name, "score": score, "note": note}
    if birth_moon_sign is not None:
        h = (p.moon_sign_index - birth_moon_sign) % 12 + 1
        score = 1 if h in CHANDRA_GOOD else -2 if h == 8 else -1 if h in CHANDRA_BAD else 0
        note = ("Chandrashtama — the Moon is 8th from your Moon, a sensitive day" if h == 8
                else "the Moon is well placed from your Moon" if score > 0
                else "the Moon is not well placed from your Moon" if score < 0 else "neutral")
        chandra = {"house": h, "score": score, "note": note}
    return {"weekday": wd, "tara": tara, "chandra": chandra}


def judge(activity: dict, p, f: dict) -> dict:
    wd, nak, tithi = f["weekday"], p.nakshatra_index, p.tithi_number
    score, why = 0, []

    def add(points: int, text: str) -> None:
        nonlocal score
        score += points
        why.append({"good": points > 0, "bad": points < 0, "text": text})

    if nak in activity["naks"]:
        add(2, f"{p.nakshatra} nakshatra suits this")
    elif nak in UGRA or nak in TIKSHNA:
        add(-2, f"{p.nakshatra} is a harsh nakshatra for new beginnings")
    else:
        add(0, f"{p.nakshatra} nakshatra is neutral for this")
    if wd in activity["good_days"]:
        add(1, f"{p.weekday} is a good day for this")
    elif wd in activity["bad_days"]:
        add(-1, f"{p.weekday} is usually avoided for this")
    if tithi == 30:
        add(-3, "Amavasya (new moon) — avoided for auspicious starts")
    elif p.tithi_paksha_index in RIKTA:
        add(-2, f"{p.paksha} {_ordinal(p.tithi_paksha_index)} is a Rikta (empty) tithi")
    elif activity.get("shukla") and p.paksha == "Shukla":
        add(1, "waxing Moon (Shukla paksha) is preferred")
    elif activity.get("shukla") and p.tithi_paksha_index >= 10:
        add(-2, "late waning Moon (Krishna paksha) is avoided for this")
    if p.yoga_number in BAD_YOGAS:
        add(-1, f"{p.yoga} yoga is inauspicious")
    if p.karana == "Vishti":
        add(-2, "Vishti (Bhadra) karana — avoid starting important work")
    # Personal strength can lift a day by at most one step but can pull it down fully.
    personal = 0
    if f["tara"]:
        t = f["tara"]
        personal += t["score"]
        why.append({"good": t["score"] > 0, "bad": t["score"] < 0, "text": f"Tara bala: {t['name']} — {t['note']}"})
    if f["chandra"] and f["chandra"]["score"]:
        c = f["chandra"]
        personal += c["score"]
        why.append({"good": c["score"] > 0, "bad": c["score"] < 0, "text": f"Chandra bala: {c['note']}"})
    score += max(-3, min(1, personal))
    key, label = _verdict(score)
    extra = None
    if activity["key"] == "travel":
        extra = f"Avoid starting a journey towards the {DISHA_SHOOL[wd]} today (Disha shool)."
    if activity["key"] == "marriage":
        extra = "Wedding dates also depend on Jupiter, Venus and the season — confirm the final date with an astrologer."
    return {"key": activity["key"], "name": activity["name"], "icon": activity["icon"], "score": score,
            "verdict": key, "label": label, "why": why, "note": extra}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def windows(p) -> dict:
    wd = C.WEEKDAY_NAMES.index(p.weekday)
    day = p.sunset - p.sunrise
    mid = p.sunrise + day / 2
    abhijit = None if wd == WED else [_iso(mid - day / 30), _iso(mid + day / 30)]
    part, start = day / 8, CHOG_ORDER.index(CHOG_START[wd])
    chog = []
    for i in range(8):
        name = CHOG_ORDER[(start + i) % 7]
        chog.append({"name": name, "quality": CHOG_QUALITY[name],
                     "start": _iso(p.sunrise + part * i), "end": _iso(p.sunrise + part * (i + 1))})
    return {
        "sunrise": _iso(p.sunrise), "sunset": _iso(p.sunset),
        "brahma": [_iso(p.sunrise - timedelta(minutes=96)), _iso(p.sunrise - timedelta(minutes=48))],
        "abhijit": abhijit,
        "rahu_kalam": [_iso(x) for x in p.rahu_kalam],
        "yamaganda": [_iso(x) for x in p.yamaganda],
        "gulika": [_iso(x) for x in p.gulika],
        "choghadiya": chog,
    }


def muhurat_days(start: date, days: int, lat: float, lon: float, tz_name: str,
                 birth_nak: int | None = None, birth_moon_sign: int | None = None) -> list[dict]:
    out = []
    for i in range(days):
        p = compute_panchang(start + timedelta(days=i), lat, lon, tz_name)
        f = day_factors(p, birth_nak, birth_moon_sign)
        acts = [judge(a, p, f) for a in ACTIVITIES]
        overall = round(sum(a["score"] for a in acts) / len(acts))
        out.append({
            "date": p.date.isoformat(), "weekday": p.weekday,
            "tithi": {"number": p.tithi_number, "paksha": p.paksha, "index": p.tithi_paksha_index,
                      "name": "Amavasya" if p.tithi_number == 30 else "Purnima" if p.tithi_number == 15
                      else f"{p.paksha} {_ordinal(p.tithi_paksha_index)}"},
            "nakshatra": p.nakshatra, "yoga": p.yoga, "karana": p.karana,
            "tara": f["tara"], "chandra": f["chandra"],
            "overall": dict(zip(("verdict", "label"), _verdict(overall))),
            "activities": acts, "windows": windows(p),
        })
    return out
