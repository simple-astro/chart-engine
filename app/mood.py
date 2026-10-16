"""State of mind: quick mood logs, each saved with that moment's astrology, so personal patterns can be checked.

A log is a feeling on a 7-step scale (-3 very unpleasant .. +3 very pleasant), a few words that describe it, and
what is having the biggest impact. With it we keep a snapshot of the day's factors for this person (Tara and
Chandra bala, the Moon's house from the lagna, tithi, nakshatra, the hora and Rahu Kaal at that moment, the
running Dasha lords and the day's rating for new starts). Patterns are only shown once there are enough logs,
with their counts, and small differences are labelled as possibly chance.

Replies are template-based (no LLM), never fatalistic, and always end with something the person can do.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

VALENCE = {-3: "Very unpleasant", -2: "Unpleasant", -1: "Slightly unpleasant", 0: "Neutral",
           1: "Slightly pleasant", 2: "Pleasant", 3: "Very pleasant"}
FEELINGS = {
    "pleasant": ["Amazed", "Amused", "Blessed", "Brave", "Calm", "Confident", "Connected", "Content", "Devoted",
                 "Energetic", "Excited", "Focused", "Grateful", "Happy", "Hopeful", "Inspired", "Joyful", "Loved",
                 "Motivated", "Peaceful", "Proud", "Relieved", "Satisfied", "Surprised"],
    "neutral": ["Bored", "Calm", "Content", "Curious", "Distracted", "Drained", "Indifferent", "Okay", "Peaceful",
                "Reflective", "Tired", "Unsure"],
    "unpleasant": ["Angry", "Annoyed", "Anxious", "Confused", "Disappointed", "Drained", "Embarrassed", "Frustrated",
                   "Guilty", "Heartbroken", "Homesick", "Hurt", "Impatient", "Insecure", "Irritated", "Jealous",
                   "Lonely", "Misunderstood", "Overwhelmed", "Restless", "Sad", "Scared", "Stressed", "Stuck",
                   "Worried"],
}
ALL_FEELINGS = sorted({f for xs in FEELINGS.values() for f in xs})
CAUSES = ["Business", "Children", "Community", "Current events", "Debt", "Education", "Family", "Fitness",
          "Food and diet", "Friends", "Health", "Hobbies", "Home and property", "In-laws", "Job search",
          "Legal matters", "Money", "Parents", "Partner and marriage", "Self care", "Sleep", "Social media",
          "Spirituality", "Travel", "Visa and immigration", "Weather", "Work"]
# Which life-area card (and Ask Astropositivism topic) a cause points to.
CAUSE_AREA = {"Work": "career", "Education": "career", "Job search": "career", "Business": "career",
              "Money": "money", "Debt": "money", "Partner and marriage": "love", "In-laws": "love",
              "Family": "home", "Parents": "home", "Children": "home", "Home and property": "home",
              "Health": "health", "Fitness": "health", "Self care": "health", "Sleep": "health",
              "Food and diet": "health"}

# A difficult feeling's traditional planet, and a habit that helps right now (the product leads with habits).
FEELING_PLANET = {"Anxious": "Moon", "Worried": "Moon", "Scared": "Moon", "Lonely": "Moon", "Sad": "Moon",
                  "Overwhelmed": "Rahu", "Angry": "Mars", "Annoyed": "Mars", "Irritated": "Mars", "Frustrated": "Mars",
                  "Jealous": "Venus", "Stressed": "Saturn", "Drained": "Saturn", "Tired": "Saturn",
                  "Disappointed": "Jupiter", "Guilty": "Jupiter",
                  "Insecure": "Moon", "Hurt": "Moon", "Homesick": "Moon", "Heartbroken": "Venus",
                  "Restless": "Rahu", "Impatient": "Mars", "Stuck": "Saturn", "Embarrassed": "Sun",
                  "Confused": "Mercury", "Misunderstood": "Mercury", "Distracted": "Mercury", "Unsure": "Mercury"}
CALM = {
    "Moon": "Five minutes of Chandra Bhedana breathing (in through the left nostril, out through the right), "
            "and a glass of water before you reply to anyone",
    "Mars": "Walk briskly or exercise for 20 minutes before you say anything you can't take back",
    "Saturn": "Finish one small pending task, then rest — slow and steady is Saturn's way",
    "Jupiter": "Talk it through with a teacher, an elder or someone wise you trust",
    "Venus": "Do one small thing you enjoy — music, a tidy room or fresh clothes — and count what you already have",
    "Rahu": "Put the phone away for an hour: no news or scrolling, and take one thing at a time",
    "Sun": "Ten minutes in sunlight, and one small thing done for yourself first",
    "Mercury": "Write it down in three short lines and choose one next step; talk it through once your thoughts settle",
}
HELPLINES = [{"region": "India", "name": "Tele-MANAS", "number": "14416"},
             {"region": "Canada and the US", "name": "Suicide and Crisis Lifeline", "number": "988"},
             {"region": "Elsewhere", "name": "your local emergency number", "number": ""}]
_CARE_WORDS = re.compile(r"hopeless|suicid|kill myself|end it all|end my life|self[- ]?harm|want to die|"
                         r"no reason to live|can'?t go on", re.I)
MIN_LOGS = 10   # before any pattern is shown
MIN_GROUP = 3   # logs needed in a group for it to be compared at all


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _hm(iso: str, tz: ZoneInfo) -> str:
    return datetime.fromisoformat(iso).astimezone(tz).strftime("%-I:%M %p")


def snapshot(profile: dict, where: dict, now: datetime) -> dict:
    """This moment's astrology for this person, saved with the log."""
    from app import today as T
    from app.transit_view import dasha_on
    chart, tz = profile["chart"], ZoneInfo(where["tz_name"])
    local = now.astimezone(tz)
    lords = {x["level"]: x["lord"] for x in dasha_on(chart, now)}
    moon, antar = chart["grahas"]["Moon"], lords.get("antar")
    g = T.today(local.date(), where["lat"], where["lon"], where["tz_name"], chart["lagna"]["sign_index"],
                moon["nakshatra_index"], moon["sign_index"], lords.get("maha"), antar,
                chart["grahas"][antar]["sign_index"] if antar in chart["grahas"] else None)
    iso = now.isoformat()
    hora = next((h["lord"] for h in g["horas"] if h["start"] <= iso < h["end"]), None)
    rk = g["rahu_kalam"]
    later = [b for b in g["best_times"] if b["end"] > iso]
    return {
        "date": local.date().isoformat(), "time": local.strftime("%H:%M"), "weekday": g["weekday"],
        "nakshatra": g["nakshatra"], "tithi": g["tithi"],
        "tara": g["tara"]["name"] if g["tara"] else None, "tara_score": g["tara"]["score"] if g["tara"] else None,
        "chandra_house": g["chandra"]["house"] if g["chandra"] else None,
        "chandra_score": g["chandra"]["score"] if g["chandra"] else None,
        "moon_house": g["moon_house"], "rating": g["rating"]["verdict"], "hora": hora,
        "rahu_kaal": rk[0] <= iso < rk[1], "maha": lords.get("maha"), "antar": antar,
        # not used for patterns; lets the reply point to the rest of today
        "_next_best": [{"label": b["label"], "span": f"{_hm(b['start'], tz)} – {_hm(b['end'], tz)}"} for b in later],
        "_rahu": f"{_hm(rk[0], tz)} – {_hm(rk[1], tz)}", "_upay": g["upay"],
    }


def _next_good_day(profile: dict, where: dict, day: date) -> dict | None:
    from app import muhurat
    moon = profile["chart"]["grahas"]["Moon"]
    days = muhurat.muhurat_days(day + timedelta(days=1), 7, where["lat"], where["lon"], where["tz_name"],
                                moon["nakshatra_index"], moon["sign_index"])
    d = next((x for x in days if x["overall"]["verdict"] in ("excellent", "good")), None)
    return d and {"date": d["date"], "weekday": d["weekday"], "label": d["overall"]["label"]}


def care_needed(valence: int, note: str | None, recent: list[dict]) -> bool:
    """Words that need a person, not astrology — or three days running of feeling unpleasant or worse."""
    if note and _CARE_WORDS.search(note):
        return True
    if valence > -2:
        return False
    worst: dict[str, int] = {}
    for r in recent:
        worst[r["local_date"]] = min(worst.get(r["local_date"], 3), r["valence"])
    last3 = sorted(worst)[-3:]
    return len(last3) == 3 and all(worst[d] <= -2 for d in last3)


def reply(profile: dict, where: dict, log: dict, care: bool) -> dict:
    """What Astropositivism says straight after a log: why today may feel this way, when to act, and one thing to do."""
    s, v, feelings = log["snapshot"], log["valence"], log["feelings"]
    unpleasant = v < 0
    sky = None
    if unpleasant:
        if s["chandra_house"] == 8:
            sky = "The Moon is 8th from your birth Moon today (Chandrashtama) — heavier, more emotional days like this are common."
        elif s["tara_score"] is not None and s["tara_score"] <= -1:
            sky = f"Your star today is {s['tara']}, a harder Tara — many people feel more friction on days like this."
        elif s["chandra_score"] is not None and s["chandra_score"] < 0:
            sky = f"The Moon is {_ord(s['chandra_house'])} from your birth Moon today, which can weigh on the mind."
        elif s["rahu_kaal"]:
            sky = "It is Rahu Kaal right now, a restless part of the day — let it pass before you decide anything."
        else:
            sky = "Nothing in today's sky explains this strongly, so it is probably about what is around you — useful to know too."
    elif v > 0:
        if s["tara_score"] is not None and s["tara_score"] > 0:
            sky = f"Your star today is {s['tara']}, a supportive Tara — the day is with you."
        elif s["chandra_score"] is not None and s["chandra_score"] > 0:
            sky = "The Moon is well placed from your birth Moon today — a good day to use."
        else:
            sky = "Good to see — today's sky is ordinary, so this is your own doing."
    nxt = s["_next_best"]
    if unpleasant:
        if nxt:
            timing = f"Leave big decisions until {nxt[0]['span']} ({nxt[0]['label']}), or until you feel steadier."
        else:
            gd = _next_good_day(profile, where, date.fromisoformat(s["date"]))
            timing = (f"Leave big decisions for another day — {gd['weekday']} {int(gd['date'][8:])} looks good for you."
                      if gd else "Leave big decisions for another day.")
        planet = next((FEELING_PLANET[f] for f in feelings if f in FEELING_PLANET), "Moon")
        do = {"planet": planet, "text": CALM[planet]}
    else:
        timing = (f"Use it: your best time for anything important today is {nxt[0]['span']} ({nxt[0]['label']})."
                  if nxt else f"Rahu Kaal today was {s['_rahu']}; the rest of the day is yours.")
        u = s["_upay"]
        do = {"planet": u["planet"], "text": f"{u['habit']} — good days are kept by giving, so share some of it"}
    area = next((CAUSE_AREA[c] for c in log["causes"] if c in CAUSE_AREA), None)
    about = ", ".join(c.lower() for c in log["causes"][:2]) or "today"
    ask = (f"I'm feeling {', '.join(f.lower() for f in feelings) or VALENCE[v].lower()} about {about}. "
           "What does my chart say about this right now, and what can I do?")
    out = {"headline": VALENCE[v], "sky": sky, "timing": timing, "do": do, "area": area, "ask": ask}
    if care:
        out["care"] = {"text": "It sounds like a lot right now. Please talk to someone you trust today — "
                               "astrology can't replace a real conversation. If you feel unsafe, call a helpline now.",
                       "helplines": HELPLINES}
    return out


def public(log: dict) -> dict:
    """A log as the app shows it: the internal reply helpers stay out."""
    return {**log, "snapshot": {k: v for k, v in log["snapshot"].items() if not k.startswith("_")}}


# ----- patterns -----
TARA_ORDER = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyak", "Sadhana", "Naidhana", "Mitra", "Param Mitra"]
RATING = {"excellent": "great days for new starts", "good": "good days for new starts",
          "fair": "'start with care' days", "avoid": "'avoid new starts' days"}


def _groups(logs: list[dict]) -> list[tuple[str, str, list[int]]]:
    """(kind, label, valences) for every factor value seen."""
    out: dict[tuple[str, str], list[int]] = {}

    def add(kind: str, label: str, v: int) -> None:
        out.setdefault((kind, label), []).append(v)

    for r in logs:
        s, v = r["snapshot"], r["valence"]
        if s.get("tara"):
            add("tara", f"your {s['tara']} Tara days", v)
        if s.get("chandra_house") == 8:
            add("chandra", "Chandrashtama days (Moon 8th from your Moon)", v)
        elif s.get("chandra_score") is not None:
            add("chandra", "days the Moon is well placed from your Moon" if s["chandra_score"] > 0
                else "days the Moon is poorly placed from your Moon" if s["chandra_score"] < 0
                else "days the Moon is neutral from your Moon", v)
        if s.get("moon_house"):
            add("moon_house", f"days the Moon passes your {_ord(s['moon_house'])} house", v)
        if s.get("weekday"):
            add("weekday", f"{s['weekday']}s", v)
        if s.get("rating"):
            add("rating", RATING[s["rating"]], v)
        if s.get("rahu_kaal"):
            add("rahu_kaal", "logs made during Rahu Kaal", v)
        for c in r["causes"]:
            add("cause", f"times {c.lower()} was the main thing on your mind", v)
    return [(k, lab, vs) for (k, lab), vs in out.items()]


def patterns(logs: list[dict]) -> dict:
    """Which factors go with a higher or lower mood than usual — with counts, and honest about chance."""
    n = len(logs)
    if n < MIN_LOGS:
        return {"ready": False, "logs": n, "needed": MIN_LOGS - n, "found": []}
    vals = [r["valence"] for r in logs]
    mean = sum(vals) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / (n - 1)) or 1.0
    found = []
    for kind, label, vs in _groups(logs):
        k = len(vs)
        if k < MIN_GROUP or k == n:
            continue
        m = sum(vs) / k
        diff = m - mean
        z = diff / (sd / math.sqrt(k))  # a rough check on whether this could just be chance
        if abs(diff) < 0.5:
            continue
        strength = "clear" if abs(z) >= 2 and k >= 5 else "possible"
        found.append({"kind": kind, "label": label, "logs": k, "average": round(m, 2), "difference": round(diff, 2),
                      "strength": strength,
                      "text": f"On {label} your mood averages {abs(diff):.1f} step{'s' if abs(diff) >= 1.05 else ''} "
                              f"{'higher' if diff > 0 else 'lower'} than usual ({k} logs)."
                              + ("" if strength == "clear" else " This could still be chance.")})
    found.sort(key=lambda x: (x["strength"] != "clear", -abs(x["difference"]) * math.sqrt(x["logs"])))
    # Does the app's own day rating match how the person felt?
    good = [r["valence"] for r in logs if r["snapshot"].get("rating") in ("excellent", "good")]
    hard = [r["valence"] for r in logs if r["snapshot"].get("rating") in ("fair", "avoid")]
    check = None
    if len(good) >= MIN_GROUP and len(hard) >= MIN_GROUP:
        d = sum(good) / len(good) - sum(hard) / len(hard)
        check = {"good_days": round(sum(good) / len(good), 2), "harder_days": round(sum(hard) / len(hard), 2),
                 "text": (f"On days we rated good for new starts you felt {d:.1f} steps better than on harder days."
                          if d >= 0.5 else
                          "So far, our day rating and your mood don't line up much — your days run on more than the sky."
                          if d > -0.5 else
                          "So far you've felt better on days we rated harder — keep logging; we'll keep checking.")}
    return {"ready": True, "logs": n, "average": round(mean, 2), "found": found[:6], "rating_check": check}


def summary_for_sukh(logs: list[dict]) -> dict | None:
    """A short, private summary for chat context (only when the person has agreed)."""
    if not logs:
        return None
    recent = [{"when": f"{r['snapshot'].get('date')} {r['snapshot'].get('time', '')}".strip(),
               "feeling": VALENCE[r["valence"]] + (": " + ", ".join(r["feelings"]) if r["feelings"] else ""),
               "about": r["causes"]} for r in logs[:7]]
    p = patterns(logs)
    return {"recent": recent, "patterns": [x["text"] for x in p["found"][:3]] if p["ready"] else [],
            "rule": "The person shared their mood log. Use it gently and only when relevant: acknowledge how they feel, "
                    "never blame the planets for their feelings, and always offer something they can do. If they sound "
                    "unsafe or hopeless, encourage them to talk to someone they trust or call a helpline "
                    "(India: Tele-MANAS 14416; Canada and the US: 988)."}
