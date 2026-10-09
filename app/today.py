"""Today for one person: the day's rating, Do's and Don'ts, best times, colour, number, direction and upay.

Everything is traditional and personalised only through the native's own chart:
- Tara bala and Chandra bala (birth star and natal Moon against today's Moon), from app.muhurat;
- functional benefics/malefics by lagna: lords of 1, 5, 9 (and a yogakaraka) help, lords of 6, 8, 12 that own
  no trikona do not — used to pick the colour, number and the best hora;
- the running Mahadasha / Antardasha lords;
- the weekday lord's traditional work, colour, number, mantra and daan, and Disha Shool.
Hora (planetary hour) runs from sunrise in the Chaldean order, starting with the weekday lord.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app import muhurat
from core import constants as C
from core.panchang import compute_panchang

DAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Sunday = 0
CHALDEAN = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
COLOUR = {"Sun": ("orange or saffron", "#e8892b"), "Moon": ("white or silver", "#e9eef2"), "Mars": ("red", "#c8342b"),
          "Mercury": ("green", "#2f9e5b"), "Jupiter": ("yellow", "#e7b928"), "Venus": ("white or light pink", "#f4c6d0"),
          "Saturn": ("dark blue or black", "#22325c")}
NUMBER = {"Sun": 1, "Moon": 2, "Jupiter": 3, "Mercury": 5, "Venus": 6, "Saturn": 8, "Mars": 9}
MANTRA = {"Sun": "Om Suryaya Namah", "Moon": "Om Chandraya Namah", "Mars": "Om Mangalaya Namah",
          "Mercury": "Om Budhaya Namah", "Jupiter": "Om Gurave Namah", "Venus": "Om Shukraya Namah",
          "Saturn": "Om Shanaye Namah"}
DAAN = {"Sun": "wheat or jaggery", "Moon": "rice or milk", "Mars": "red lentils (masoor)", "Mercury": "green moong",
        "Jupiter": "chana dal, turmeric or bananas", "Venus": "white sweets or curd", "Saturn": "black sesame or mustard oil"}
# Disha Shool: what to eat or do before setting out if the journey can't wait.
SHOOL_FIX = ["eat a little ghee or daliya", "look in a mirror or drink milk", "eat a little jaggery (gud)",
             "eat coriander seeds or sesame (til)", "eat a little curd (dahi)", "eat a little barley (jau) or curd",
             "eat a little ginger or urad dal"]
DAY_WORK = {
    "Sun": ["Government or official work", "Meet seniors, or call your father", "Start a health routine"],
    "Moon": ["Family time — call your mother", "Calm, creative work and rest", "Buy household things or clothes"],
    "Mars": ["Property, repairs or physical work", "Exercise or sport", "Face a hard problem head-on"],
    "Mercury": ["Paperwork, emails and contracts", "Study, writing or trade", "Calls and networking"],
    "Jupiter": ["Learning, teaching or asking for advice", "Plan your finances or investments", "Visit a place of worship; respect elders"],
    "Venus": ["Shopping, arts and beauty", "Time with your partner", "Social plans and celebrations"],
    "Saturn": ["Finish pending work", "Cleaning, repairs and service", "Help workers or someone in need"],
}
# Today's Moon counted from the natal Moon: what that house invites (good) or warns about.
MOON_DO = {1: "Put yourself first — health and appearance", 3: "Take initiative; short trips and calls go well",
           6: "Clear debts, tasks and competition", 7: "Meetings and partnerships go well",
           10: "Push at work — visibility is high", 11: "Ask for what you want; gains and networking"}
MOON_AVOID = {4: "Arguments at home; keep your mind calm", 8: "Big decisions, risky drives and quarrels (Chandrashtama)",
              12: "Overspending and late nights"}
DASHA_LINE = {
    "Sun": "Your Sun period rewards leadership and dealing with authority",
    "Moon": "Your Moon period puts home, mind and family first",
    "Mars": "Your Mars period rewards courage, property and hard effort",
    "Mercury": "Your Mercury period rewards paperwork, study and clear talk",
    "Jupiter": "Your Jupiter period rewards learning, good advice and patience",
    "Venus": "Your Venus period favours comfort, relationships and money matters",
    "Saturn": "Your Saturn period rewards discipline and steady, honest work",
    "Rahu": "Your Rahu period brings big ambitions — stay away from shortcuts",
    "Ketu": "Your Ketu period favours inner work over chasing results",
}


def chart_planets(lagna_sign: int) -> tuple[list[str], set[str]]:
    """(helpful planets in order of strength, difficult planets) for this lagna."""
    lord = lambda h: C.SIGN_LORDS[(lagna_sign + h - 1) % 12]
    owned: dict[str, set[int]] = {}
    for h in range(1, 13):
        owned.setdefault(lord(h), set()).add(h)
    yogakaraka = [p for p, hs in owned.items() if hs & {4, 10} and hs & {5, 9}]
    good = list(dict.fromkeys(yogakaraka + [lord(1), lord(9), lord(5)]))
    bad = {p for p, hs in owned.items() if hs & {6, 8, 12} and not hs & {1, 5, 9}}
    return good, bad


def horas(p, next_sunrise: datetime) -> list[dict]:
    """24 planetary hours: 12 from sunrise to sunset, 12 from sunset to the next sunrise."""
    lord0 = CHALDEAN.index(DAY_LORD[C.WEEKDAY_NAMES.index(p.weekday)])
    out, day, night = [], (p.sunset - p.sunrise) / 12, (next_sunrise - p.sunset) / 12
    edge = lambda i: p.sunrise + day * i if i < 12 else p.sunset + night * (i - 12) if i < 24 else next_sunrise
    for i in range(24):
        out.append({"lord": CHALDEAN[(lord0 + i) % 7], "start": edge(i).isoformat(), "end": edge(i + 1).isoformat()})
    return out


def _overlap(a: dict, b: dict) -> dict | None:
    s, e = max(a["start"], b["start"]), min(a["end"], b["end"])
    return {"start": s, "end": e} if s < e else None


def best_times(windows: dict, hs: list[dict], good: list[str]) -> list[dict]:
    """Auspicious windows that fall in a hora of one of the native's helpful planets; else the plain windows."""
    bad = sorted(tuple(windows[k]) for k in ("rahu_kalam", "yamaganda"))
    clean = []
    for w in muhurat.good_windows(windows):  # Abhijit is not checked there; trim every window around the bad periods
        s = w["start"]
        for a, b in bad:
            if a < w["end"] and b > s:
                if a > s:
                    clean.append({**w, "start": s, "end": a})
                s = max(s, b)
        if s < w["end"]:
            clean.append({**w, "start": s})
    span = lambda x: datetime.fromisoformat(x["end"]) - datetime.fromisoformat(x["start"])
    clean = [w for w in clean if span(w) >= timedelta(minutes=20)]
    picks = []
    for w in clean:
        for h in hs[:12]:
            if h["lord"] in good and (o := _overlap(w, h)):
                if (datetime.fromisoformat(o["end"]) - datetime.fromisoformat(o["start"])) >= timedelta(minutes=20):
                    picks.append({**o, "label": f"{w['name']} · {h['lord']} hora", "hora": h["lord"],
                                  "rank": (not w["best"], good.index(h["lord"]))})
    if not picks:
        picks = [{"start": w["start"], "end": w["end"], "label": w["name"], "hora": None, "rank": (not w["best"], 9)}
                 for w in clean]
    picks.sort(key=lambda x: x["rank"])
    out = sorted(picks[:2], key=lambda x: x["start"])
    return [{k: v for k, v in x.items() if k != "rank"} for x in out]


def today(day: date, lat: float, lon: float, tz_name: str, lagna_sign: int, birth_nakshatra: int, birth_moon_sign: int,
          maha: str | None = None, antar: str | None = None) -> dict:
    p = compute_panchang(day, lat, lon, tz_name)
    nxt = compute_panchang(day + timedelta(days=1), lat, lon, tz_name)
    f = muhurat.day_factors(p, birth_nakshatra, birth_moon_sign)
    acts = [muhurat.judge(a, p, f) for a in muhurat.ACTIVITIES]
    overall = muhurat._verdict(round(sum(a["score"] for a in acts) / len(acts)))
    w = muhurat.windows(p)
    wd = f["weekday"]
    lord = DAY_LORD[wd]
    good, bad = chart_planets(lagna_sign)
    tara, chandra = f["tara"], f["chandra"]

    # Why the day is rated as it is: the strongest personal factor first.
    if chandra and chandra["house"] == 8:
        why = "the Moon is 8th from your Moon (Chandrashtama) — keep big decisions for another day"
    elif tara and tara["score"] <= -1:
        why = f"your star today is {tara['name']} ({tara['note'].split(' — ')[0]}) — go steady"
    elif p.tithi_number == 30:
        why = "it is Amavasya — good for prayer and rest, not new starts"
    elif overall[0] in ("fair", "avoid") and (drag := next(iter(
            (["Bhadra (Vishti karana) slows new work"] if p.karana == "Vishti" else [])
            + ([f"{p.paksha} {muhurat._ordinal(p.tithi_paksha_index)} is a Rikta (empty) tithi"]
               if p.tithi_paksha_index in muhurat.RIKTA else [])
            + ([f"{p.yoga} yoga is inauspicious"] if p.yoga_number in muhurat.BAD_YOGAS else [])
            + ([f"{p.nakshatra} is a harsh nakshatra for new beginnings"]
               if p.nakshatra_index in muhurat.UGRA | muhurat.TIKSHNA else [])), None)):
        good_bit = (f"your star is {tara['name']}, but " if tara and tara["score"] > 0 else "")
        why = good_bit + drag
    elif tara and tara["score"] > 0 and chandra and chandra["score"] > 0:
        why = f"your star is {tara['name']} and the Moon is well placed from your Moon"
    else:
        why = (f"{tara['name']} star" if tara else p.nakshatra) + (
            f", but {chandra['note']}" if chandra and chandra["score"] < 0 else f", and {chandra['note']}" if chandra and chandra["score"] else "")

    dos = [MOON_DO[chandra["house"]]] if chandra and chandra["house"] in MOON_DO else []
    dos += DAY_WORK[lord]
    best_acts = [a["name"] for a in acts if a["verdict"] in ("excellent", "good")]
    dos = dos[:2] + ([f"Good for: {', '.join(best_acts[:2]).lower()}"] if best_acts else dos[2:3])

    avoid = [MOON_AVOID[chandra["house"]]] if chandra and chandra["house"] in MOON_AVOID else []
    if tara and tara["score"] <= -1:
        avoid.append("Starting anything big — your star today is " + tara["name"])
    if p.karana == "Vishti":
        avoid.append("Important new work (Bhadra / Vishti karana)")
    bad_acts = [a["name"] for a in acts if a["verdict"] == "avoid"]
    if bad_acts:
        avoid.append(" and ".join([bad_acts[0]] + [x.lower() for x in bad_acts[1:2]]))
    avoid.append("Starting new work during Rahu Kaal")
    avoid = avoid[:3]

    wear = lord if lord not in bad else good[0]
    colour = {"planet": wear, "name": COLOUR[wear][0], "hex": COLOUR[wear][1],
              "why": (f"{p.weekday}'s colour ({lord})" if wear == lord else
                      f"{lord} rules {p.weekday} but is a difficult planet for your lagna, so wear your lagna lord {wear}'s colour"),
              "avoid": COLOUR[lord][0] if wear != lord else None}
    hs = horas(p, nxt.sunrise)
    dl = [x for x in (maha, antar) if x]
    upay_planet = next((x for x in dl[::-1] if x == lord), lord)
    upay = {"planet": upay_planet, "mantra": MANTRA[upay_planet], "daan": DAAN[upay_planet],
            "why": (f"{lord} rules today and also runs your {'Antardasha' if lord == antar else 'Mahadasha'}"
                    if lord in dl else f"{lord} rules {p.weekday}")}
    line = DASHA_LINE.get(antar or maha or "", "")
    if line:
        line += (" — and today is its own day, a good one to push." if (antar or maha) == lord
                 else " — use today's best time for anything important.")
    return {
        "date": day.isoformat(), "tz": tz_name, "weekday": p.weekday, "tithi": p.tithi_number, "nakshatra": p.nakshatra,
        "rating": {"verdict": overall[0], "label": overall[1], "why": why},
        "tara": tara, "chandra": chandra, "sukh": line, "do": dos[:3], "avoid": avoid,
        "best_times": best_times(w, hs, good), "rahu_kalam": w["rahu_kalam"], "yamaganda": w["yamaganda"],
        "colour": colour, "number": {"value": NUMBER[wear], "planet": wear},
        "direction": {"avoid": muhurat.DISHA_SHOOL[wd], "fix": SHOOL_FIX[wd]},
        "upay": upay, "horas": hs, "helpful": good, "difficult": sorted(bad),
    }
