"""Coming up for you: the next changes in a person's life seasons, in plain words.

Two kinds, labelled honestly:
- Period changes ("strong"): the next Dasha sub-periods, and any Antardasha / Mahadasha change within a year.
  For each we say which life matters the new period supports, by the same Promise -> Dasha rules the dated-event
  backtest supports (core.kp_predict).
- Sky changes ("hint"): in the next 90 days, only the slow-planet moves that matter to this person — Saturn and
  Jupiter changing sign (read from the natal Moon: Sade Sati, Ashtama Shani, Jupiter's gochara), and their
  Dasha lords changing sign or turning direct. Exact-day transit timing tested at chance, so these stay hints.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from core import kp_predict as K
from core.transit_scan import scan_events

GOOD_FOR = {  # life matter -> (how people say it, what to do in a good stretch)
    "career": ("career", "push at work — apply, ask, or take on more"),
    "money": ("money", "ask for what you're owed and save the extra"),
    "marriage": ("marriage", "marriage talks and family meetings go well"),
    "love": ("love", "make time for your partner"),
    "job_change": ("a job change", "a good window to switch jobs"),
    "business": ("business", "start or grow a business"),
    "property": ("property", "look at property — papers move"),
    "vehicle": ("buying a vehicle", "a good time to buy a vehicle"),
    "foreign": ("travel abroad", "plan travel or visa work"),
    "education": ("studies", "study and finish courses"),
    "exams": ("exams and interviews", "sit exams and interviews"),
    "children": ("children", "a good time for family plans"),
    "health": ("health", "start a health routine — recovery is supported"),
    "awards": ("recognition", "put your work forward"),
    "residence": ("moving house", "moving house goes smoothly"),
}
TAKE_CARE = {"illness": "health", "accident": "driving and risky activities"}
ORDER = list(GOOD_FOR)
HOUSE = {1: "self and health", 2: "money and family", 3: "effort, courage and siblings", 4: "home, mother and peace",
         5: "children, studies and romance", 6: "work, debts and health", 7: "marriage and partners",
         8: "sudden changes and in-laws", 9: "luck, father and faith", 10: "career and status",
         11: "gains and friends", 12: "expenses, travel and rest"}
SATURN_MOON = {  # Saturn's sign counted from the natal Moon
    12: ("Sade Sati begins", "a slower, more serious 7½ years starts with its first phase — build habits, not shortcuts"),
    1: ("Sade Sati: the middle phase begins", "the most demanding phase — keep routines steady and health first"),
    2: ("Sade Sati: the last phase begins", "the load starts to lift; money and family need care"),
    3: ("Sade Sati ends", "a heavier stretch closes — effort starts to pay more easily"),
    8: ("Ashtama Shani begins", "Saturn 8th from your Moon: go slowly with big risks and keep health first"),
    9: ("Ashtama Shani ends", "the 8th-house Saturn stretch closes"),
}
JUPITER_GOOD = {2, 5, 7, 9, 11}  # Jupiter's classical good houses from the Moon (gochara)
SKY_DO = {"Saturn": "take on less, finish what you start, and help someone who works hard for little",
          "Jupiter": "learn something, ask a mentor, and respect teachers and elders",
          "Rahu": "avoid shortcuts and too much screen time; stay grounded",
          "Ketu": "simplify and let go of what's done"}


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _verdicts(chart: dict, per: dict) -> dict[str, str]:
    """Every life matter's verdict in one period."""
    out = {}
    for t in list(GOOD_FOR) + list(TAKE_CARE):
        _, _, _, _, karakas, required, _ = K.TOPICS[t]
        js = {lvl: K.lord_verdict(chart, t, per[lvl]) for lvl in ("maha", "antar", "praty")}
        out[t], _ = K.dba_verdict(js, required, K.karaka_present(chart, [per[l] for l in js], karakas), karakas)
    return out


CHILD_OK = {"education", "exams", "health", "foreign", "awards"}
SENIOR_SKIP = {"exams", "job_change", "education"}


def _fits_age(topic: str, age: float | None) -> bool:
    if age is None:
        return True
    if age < 18:
        return topic in CHILD_OK
    return not (age >= 60 and topic in SENIOR_SKIP)


def period_items(chart: dict, today: date, horizon_days: int = 90, chapter_days: int = 365,
                 age: float | None = None) -> list[dict]:
    pers = K.periods_in(chart, today - timedelta(days=1), today + timedelta(days=chapter_days))
    if not pers:
        return []
    now = next((p for p in pers if p["starts"] <= today < p["ends"]), pers[0])
    before = _verdicts(chart, now)
    items, small, used = [], 0, set()
    for prev, p in zip(pers, pers[1:]):
        if p["starts"] <= today:
            continue
        level = "maha" if p["maha"] != prev["maha"] else "antar" if p["antar"] != prev["antar"] else "praty"
        if level == "praty" and ((p["starts"] - today).days > horizon_days or small >= 2):
            continue
        small += level == "praty"
        v = _verdicts(chart, p)
        good = [t for t in ORDER if v[t] in ("strong", "favourable") and _fits_age(t, age)]
        good.sort(key=lambda t: v[t] != "strong")
        new = [t for t in good if before[t] not in ("strong", "favourable")]
        care = [TAKE_CARE[t] for t in TAKE_CARE if v[t] == "strong" and before[t] != "strong"]  # only a new risk
        names = {"maha": p["maha"], "antar": f"{p['maha']}–{p['antar']}", "praty": f"{p['maha']}–{p['antar']}–{p['praty']}"}[level]
        title = {"maha": f"A new life chapter: your {p['maha']} Mahadasha begins",
                 "antar": f"A new chapter: your {p['maha']}–{p['antar']} period begins",
                 "praty": f"A new stretch: the {p['praty']} sub-period begins"}[level]
        until = {"maha": None, "antar": None, "praty": p["ends"]}[level]
        if level != "praty":  # the chapter's own end date, not its first sub-period's
            span = [q for q in K.periods_in(chart, p["starts"], p["starts"] + timedelta(days=7400))
                    if q["maha"] == p["maha"] and (level == "maha" or q["antar"] == p["antar"])]
            until = span[-1]["ends"] if span else p["ends"]
        meaning = ("Good for " + ", ".join(GOOD_FOR[t][0] for t in good[:3]) + "." if good
                   else "A quieter stretch — keep to routine and steady work.")
        if care:
            meaning += f" Take care with {' and '.join(care)}."
        shown = good[:3]
        tip = next((t for t in [x for x in new if x in shown] + shown if t not in used), shown[0] if shown else None)
        used.add(tip)
        before = v
        items.append({
            "kind": "period", "level": level, "confidence": "strong", "date": p["starts"].isoformat(),
            "until": until.isoformat(), "title": title, "period": names, "meaning": meaning,
            "prepare": (GOOD_FOR[tip][1][0].upper() + GOOD_FOR[tip][1][1:] + ".") if tip else
                       "Finish pending work before it starts.",
            "new_strengths": [GOOD_FOR[t][0] for t in new], "good_for": [GOOD_FOR[t][0] for t in good],
            "ask": f"My {names} period begins on {p['starts'].strftime('%-d %B %Y')}. What will it bring for me, and how should I prepare?",
        })
    return items


@lru_cache(maxsize=64)
def _sky(start: date, days: int, ayanamsha: str, node_type: str) -> tuple:
    """The slow-planet events for everyone in a window (same for all charts with these settings)."""
    evs = scan_events(datetime.combine(start, time(0), timezone.utc), days=days, ayanamsha=ayanamsha, node_type=node_type)
    return tuple(e for e in evs if e.planet in ("Jupiter", "Saturn", "Rahu", "Ketu") and e.type in ("ingress", "station"))


def sky_items(chart: dict, today: date, lords: dict, tz: ZoneInfo, days: int = 90) -> list[dict]:
    L, moon = chart["lagna"]["sign_index"], chart["grahas"]["Moon"]["sign_index"]
    role = {lords[k]: n for k, n in (("antar", "Antardasha"), ("maha", "Mahadasha")) if lords.get(k)}
    items = []
    for e in _sky(today, days, chart["meta"].get("ayanamsha", "krishnamurti"), chart["meta"].get("node_type", "mean")):
        when = e.exact_at_utc.astimezone(tz).date()
        if when <= today:
            continue
        p, mine = e.planet, role.get(e.planet)
        lord_of = f"{p}, your {mine} lord," if mine else p
        if e.type == "station":
            if not mine or e.detail["direction"] != "direct":
                continue  # a retrograde Jupiter or Saturn carries no transit meaning (Taneja); its return does
            title = f"{p}, your {mine} lord, turns direct"
            meaning = f"Its pause ends and its effects in your life move forward again."
        else:
            to = e.detail["to_sign_index"]
            h, hm = (to - L) % 12 + 1, (to - moon) % 12 + 1
            if p == "Saturn" and hm in SATURN_MOON:
                title, meaning = SATURN_MOON[hm]
                meaning = meaning[0].upper() + meaning[1:] + "."
            elif p == "Jupiter" and (mine or hm == 1 or hm in JUPITER_GOOD):
                title = f"{lord_of} moves into your {_ord(h)} house"
                meaning = (f"{HOUSE[h][0].upper() + HOUSE[h][1:]} get Jupiter's {'protection' if h in (6, 8, 12) else 'support'}"
                           + (" — and it is a good position from your Moon." if hm in JUPITER_GOOD else
                              " — Jupiter passes over your Moon: a year of growth, keep your weight and spending in check." if hm == 1
                              else "."))
            elif mine:
                title = f"{lord_of} moves into your {_ord(h)} house"
                meaning = f"Your {mine.lower()} lord now works through {HOUSE[h]}."
            else:
                continue
            if e.detail.get("direction") == "retrograde" and p not in ("Rahu", "Ketu"):  # the nodes always move backwards
                meaning += " It is moving backwards, so this settles when it turns direct."
        items.append({"kind": "sky", "confidence": "hint", "date": when.isoformat(), "planet": p, "title": title,
                      "meaning": meaning, "prepare": SKY_DO[p][0].upper() + SKY_DO[p][1:] + ".",
                      "ask": f"{title} on {when.strftime('%-d %B %Y')}. What does it mean for me, and what should I do?"})
    # A planet can cross back and forth: keep its first crossing into each sign only.
    seen, out = set(), []
    for it in items:
        k = (it["title"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def upcoming(profile: dict, today: date, tz_name: str) -> dict:
    from app.transit_view import dasha_on
    chart, tz = profile["chart"], ZoneInfo(tz_name)
    lords = {x["level"]: x["lord"] for x in dasha_on(chart, datetime.combine(today, time(12), tz))}
    dob = (profile.get("request") or {}).get("dob")
    age = (today - date.fromisoformat(dob)).days / 365.25 if dob else None
    items = period_items(chart, today, age=age) + sky_items(chart, today, lords, tz)
    items.sort(key=lambda x: (x["date"], x["kind"] != "period"))
    return {"today": today.isoformat(), "items": items,
            "note": "Period changes follow your Dasha (well supported in our tests). Sky changes are hints: exact days "
                    "matter less than the period you are in."}
