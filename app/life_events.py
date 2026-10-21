"""Life events: what really happened in a person's life, checked against their chart.

Each event is a kind (in plain words), a date and how exact it is (day, month or year). For each one we look
at the Dasha periods running then and ask whether they supported that life matter (the same Promise -> Dasha
rules as the predictions, core.kp_predict). To keep this honest we also work out how often a random date in
the person's adult life would have "fitted", so the summary can say how many events chance alone would explain.

The events also grow the real-life backtest (admin: fits against chance across everyone, no names).
"""
from __future__ import annotations

from datetime import date, timedelta

from core import kp_predict as K

# kind: (what the person sees, the life matter it tests). Matters in K.LOOKBACK are read for past events only.
KINDS = {
    "married": ("Got married", "marriage"),
    "engaged": ("Got engaged", "marriage"),
    "love": ("Started a love affair", "love"),
    "child": ("Child born", "children"),
    "job": ("Started a job", "career"),
    "promotion": ("Promotion or raise", "career"),
    "job_change": ("Changed job", "job_change"),
    "job_loss": ("Lost a job or business loss", "career_loss"),
    "business": ("Started a business", "business"),
    "money_earned": ("Received a large sum: earned", "money"),
    "windfall": ("Received a large sum: unexpected (inheritance, windfall)", "windfall"),
    "debt_cleared": ("Cleared a big loan or debt", "money"),
    "money_loss": ("Lost money, theft or fraud", "money_loss"),
    "home": ("Bought a home or property", "property"),
    "sold": ("Sold a property", "property_sale"),
    "vehicle": ("Bought a vehicle", "vehicle"),
    "moved": ("Moved house", "residence"),
    "away": ("Started living away from home", "residence"),
    "abroad": ("Moved or went abroad", "foreign"),
    "long_journey": ("A long journey", "long_journey"),
    "family_trip": ("A family trip or holiday", "pleasure_trip"),
    "school": ("Finished school (10th or 12th)", "education"),
    "degree": ("Degree or exam passed", "education"),
    "award": ("Award or recognition", "awards"),
    "court_win": ("Won a court case", "litigation_win"),
    "pilgrimage": ("A major shrine visit or pilgrimage", "pilgrimage"),
    "initiation": ("Spiritual initiation (deeksha, a guru)", "spiritual"),
    "illness": ("Illness or surgery", "illness"),
    "accident": ("Accident or injury", "accident"),
    "parent_illness": ("A parent's major illness or surgery", None),
    "separation": ("Separation or divorce", "divorce"),
    # Recorded with care but never read against the chart: the app makes no predictions about death, so loss has
    # no life matter in the timing engine and is left out of the fit score, accuracy and rectification.
    "loss": ("Loss of a family member", None),
}
NOTED = "Recorded with care. We don't read the chart for loss, so this event isn't checked against it."
NOTED_PARENT = ("Recorded with care. A parent's health is read from their own chart, so this event isn't checked "
                "against yours.")
# How the "What happened?" choices are grouped in the form.
GROUPS = [("Relationships", ["married", "engaged", "love", "separation"]),
          ("Work and money", ["job", "promotion", "job_change", "job_loss", "business", "money_earned", "windfall",
                              "debt_cleared", "money_loss", "court_win"]),
          ("Home and travel", ["home", "sold", "vehicle", "moved", "away", "abroad", "long_journey", "family_trip"]),
          ("Studies", ["school", "degree", "award"]),
          ("Health", ["illness", "accident"]),
          ("Spiritual", ["pilgrimage", "initiation"]),
          ("Family", ["child", "parent_illness", "loss"])]


def checked(events: list[dict]) -> list[dict]:
    """The events that are read against the chart (not the ones only recorded, like a loss)."""
    return [e for e in events if KINDS[e["kind"]][1]]
GOOD = ("strong", "favourable")
LORD_OK = ("supports", "leans good")


def span(d: date, precision: str) -> tuple[date, date]:
    """The days the event could have happened on: one day, that month, or that year."""
    if precision == "day":
        return d, d + timedelta(days=1)
    if precision == "month":
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        return date(d.year, d.month, 1), nxt
    return date(d.year, 1, 1), date(d.year + 1, 1, 1)


def _share(spans: list[dict], lo: date, hi: date) -> float:
    """Fraction of [lo, hi) covered by periods that support the matter."""
    total = (hi - lo).days or 1
    good = sum(max(0, (min(p["ends"], hi) - max(p["starts"], lo)).days) for p in spans if p["verdict"] in GOOD)
    return good / total


def _base_rate(chart: dict, topic: str, birth: date, today: date) -> float:
    """How much of adult life (from 16, or from birth for a child's events) supports this matter: chance level."""
    lo = birth + timedelta(days=round(16 * 365.25))
    if lo >= today:
        lo = birth
    return _share(K.verdict_spans(chart, topic, lo, today), lo, today)


def _held_back(at: dict) -> str:
    """Lord by lord: the houses each links to for the matter, and what its sub lord brings against it."""
    out = []
    for lvl in ("maha", "antar", "praty"):
        j = at["lords"][lvl]
        if j["lord"] in (x.split(" ")[0] for x in out):
            continue
        lv = j["levels"]
        pro = sorted(set(lv["planet"]["for"]) | set(lv["nakshatra"]["for"]))
        con = lv["sub"]["against"]
        hs = lambda h: ", ".join(map(str, h))
        word = lambda h: "house" if len(h) == 1 else "houses"
        if pro and con:
            out.append(f"{j['lord']} links to {word(pro)} {hs(pro)}, but its sub lord {lv['sub']['lord']} brings {hs(con)}")
        elif pro:
            out.append(f"{j['lord']} links to {word(pro)} {hs(pro)}, not enough on its own")
        elif con:
            out.append(f"{j['lord']}'s sub lord {lv['sub']['lord']} brings {hs(con)}, against it")
        else:
            out.append(f"{j['lord']} has no link to it")
    return ". " + "; ".join(out) if out else ""


def check(chart: dict, kind: str, d: date, precision: str) -> dict:
    """Did the chart's periods support this event when it happened?"""
    label, topic = KINDS[kind]
    if topic is None:
        return {"topic": None, "fit": "noted", "share": None, "period": None, "rough": False,
                "why": NOTED_PARENT if kind == "parent_illness" else NOTED}
    lo, hi = span(d, precision)
    spans = K.verdict_spans(chart, topic, lo, hi)
    share = _share(spans, lo, hi)
    fit = "fits" if share >= 0.5 else "partly" if share > 0 else "no"
    mid = lo + (hi - lo) / 2
    at = next((p for p in spans if p["starts"] <= mid < p["ends"]), spans[0] if spans else None)
    why = None
    if at:
        names = [at["maha"], at["antar"], at["praty"]]
        helpers = list(dict.fromkeys(j["lord"] for j in at["lords"].values() if j["verdict"] in LORD_OK))
        period = "–".join(names)
        risk = K.ALL_TOPICS[topic][6] == "risk"
        what = K.ALL_TOPICS[topic][0].lower()
        verb = "point" if len(helpers) > 1 else "points"
        if not helpers:
            why = f"{period} period: none of these lords is strong enough for {what}" + _held_back(at)
        elif at["verdict"] in GOOD:
            why = f"{period} period: {', '.join(helpers)} {verb} to {what}" + (
                " — your chart showed a time to take care" if risk else "")
        else:
            why = f"{period} period: only {', '.join(helpers)} {verb} to {what}, not enough on its own"
    if why and topic in K.PENDING_REVIEW:
        why += " (the houses for this kind of event are waiting for our astrologers' review)"
    return {"topic": topic, "fit": fit, "share": round(share, 2), "period": at and "–".join([at["maha"], at["antar"], at["praty"]]),
            "why": why, "rough": precision == "year"}


def summary(chart: dict, events: list[dict], birth: date, today: date) -> dict | None:
    """How many events the chart explains, against how many chance would explain."""
    events = checked(events)
    if not events:
        return None
    fits = sum(1 for e in events if e["check"]["fit"] == "fits")
    base: dict[str, float] = {}
    for e in events:
        t = e["check"]["topic"]
        if t not in base:
            base[t] = _base_rate(chart, t, birth, today)
    expected = sum(base[e["check"]["topic"]] for e in events)
    n = len(events)
    text = f"Your chart explains {fits} of your {n} event{'s' if n > 1 else ''}."
    if n >= 3:
        text += (f" By chance, about {expected:.0f} would fit." if expected >= 0.5 else " By chance, almost none would.")
        if fits >= expected + 1.5:
            verdict = "good"
        elif fits <= expected - 1:
            verdict = "weak"
        else:
            verdict = "chance"
    else:
        text += " Add a few more to compare with chance."
        verdict = None
    return {"fits": fits, "events": n, "expected": round(expected, 1), "verdict": verdict, "text": text,
            "note": {"good": "That's well above chance — your chart and your life line up.",
                     "chance": "That's close to chance. The dates may be rough, or the birth time a little off.",
                     "weak": "That's fewer than chance — worth double-checking your birth time."}.get(verdict)}


LEVELS = ["Rough", "Fair", "Good", "Strong"]


def accuracy(chart: dict, events: list[dict], summ: dict | None, tob_unknown: bool, rectified: bool) -> dict:
    """How well the person's events let us check their chart: Rough, Fair, Good or Strong, with one next step.

    It is about how well we can check the chart, never a grade of the chart. Rough: fewer than 3 events with the
    month, or no birth time. Fair: 3+. Good: 6+ in 2 or more Mahadashas, fitting better than chance. Strong: 8+ in
    2 or more Mahadashas, well above chance, and the birth time rectified (the saved time is among the best fits).
    """
    from datetime import datetime, time as dtime
    dated = [e for e in checked(events) if e.get("precision") in ("day", "month")]

    def maha(d: str) -> str | None:
        iso = datetime.combine(date.fromisoformat(d), dtime(12)).isoformat()
        return next((x["lord"] for x in chart.get("dasha", []) if x["start"][:19] <= iso < x["end"][:19]), None)
    mahas = sorted({m for m in (maha(e["date"]) for e in dated) if m})
    fits, expected = (summ or {}).get("fits", 0), (summ or {}).get("expected", 0)
    above = len(dated) >= 3 and fits >= expected + 0.5
    well_above = (summ or {}).get("verdict") == "good"
    if tob_unknown or len(dated) < 3:
        lvl = 0
    elif len(dated) >= 8 and len(mahas) >= 2 and well_above and rectified:
        lvl = 3
    elif len(dated) >= 6 and len(mahas) >= 2 and above:
        lvl = 2
    else:
        lvl = 1
    first = mahas[0] if mahas else None
    if tob_unknown and len(dated) >= 4:
        step = ("find", "Find your birth time from your events",
                "Your events can narrow it to a part of the day. It is a hint, not a certainty.")
    elif tob_unknown:
        step = ("time", "Add your birth time", "Even an approximate time, like “around 2 PM”, lets us check your chart. "
                                               "Or add 4 events with the month and we will look for it.")
    elif len(dated) < 3:
        need = 3 - len(dated)
        step = ("event", f"Add {need} past event{'s' if need > 1 else ''} with the month",
                "A job, a wedding, a move or a degree — anything you remember the month of.")
    elif len(mahas) < 2:
        step = ("event", f"Add one event from before your {first} period" if first else "Add an event from earlier years",
                f"All your events fall in your {first} period, so they can't tell your birth time from a few minutes "
                "either side. Finishing school, a move or an illness from earlier years helps most." if first else
                "Events from different periods of your life make the check firmer.")
    elif len(dated) < 8:
        need = 8 - len(dated)
        step = ("event", f"Add {need} more event{'s' if need > 1 else ''}", "More events make the check firmer.")
    elif not rectified:
        step = ("rect", "Run Birth time rectification", "Your events span more than one period, so the result means something now.")
    elif not well_above:
        step = ("event", "Add events you remember well", "Exact months help most; check that the dates you added are right.")
    else:
        step = None
    why = (["We need your birth time to check your chart." if tob_unknown else
            "Add a few past events and we can start checking your chart against your life."][0] if lvl == 0 else
           f"{len(dated)} events, all in your {first} period. About {expected:.0f} of {len(dated)} would fit by chance, "
           "so they can't test your chart much yet." if len(mahas) < 2 else
           f"{len(dated)} events across {len(mahas)} periods; {fits} fit, against about {expected:.0f} by chance.")
    return {"level": lvl, "label": LEVELS[lvl], "levels": LEVELS, "why": why,
            "checks": [{"ok": len(dated) >= 3, "text": "At least 3 events with the month"},
                       {"ok": len(mahas) >= 2, "text": "Events in 2 or more Dasha periods"},
                       {"ok": len(dated) >= 8, "text": "8 or more events"},
                       {"ok": rectified, "text": "Birth time rectified"}],
            "next": {"action": step[0], "title": step[1], "text": step[2]} if step else None}


def birth_time_check(request: dict, events: list[dict], chart_at, today: date, span_min: int = 60,
                     step_min: int = 4, between: tuple[int, int] | None = None, unknown: bool = False) -> dict:
    """Birth time rectification: the person's events judged against charts cast a few minutes earlier and later.

    ``chart_at(tob)`` returns the chart (with extras) for the same birth with another time of birth. Only the
    time changes; place, date and ayanamsha stay as saved. Times that would cross midnight are left out.
    A best window is the run of times with the most fits; how much it means depends on how many Dasha
    lords the events span and on how many would fit by chance, so the result says that plainly.

    ``between`` (minutes after midnight, inclusive) searches that part of the day instead of an hour either side
    of the saved time; with ``unknown`` there is no saved time at all. Both are "wide" searches: they also say
    how many times of day fit almost as well as the best, because events that fit most of the day narrow nothing.
    """
    from datetime import datetime, time as dtime
    events = checked(events)
    wide = unknown or between is not None
    if unknown or between is not None:
        lo, hi = between or (0, 24 * 60 - 1)
        times = [(t, t - (lo + hi) // 2) for t in range(lo, hi + 1, step_min)]
        now = None
    else:
        h, m = map(int, request["tob"][:5].split(":"))
        now = h * 60 + m
        times = [(now + off, off) for off in range(-span_min, span_min + 1, step_min)]
    birth = date.fromisoformat(request["dob"])
    rows = []
    for t, off in times:
        if not 0 <= t < 24 * 60:
            continue
        tob = f"{t // 60:02d}:{t % 60:02d}"
        c = chart_at(tob + ":00")
        marks = [check(c, e["kind"], date.fromisoformat(e["date"]), e["precision"])["fit"] for e in events]
        rows.append({"tob": tob, "offset": off, "fits": marks.count("fits"), "marks": marks,
                     "yours": not wide and off == 0, "lagna": c["lagna"]["sign"], "chart": c})
    best = max(r["fits"] for r in rows)
    # The longest run of neighbouring times at the best score (closest to the saved time when tied).
    runs, cur = [], []
    for r in rows:
        if r["fits"] == best:
            cur.append(r)
        else:
            cur and runs.append(cur); cur = []
    cur and runs.append(cur)
    run = max(runs, key=lambda x: (len(x), -min(abs(r["offset"]) for r in x)))
    mid = min(run[(len(run) - 1) // 2:len(run) // 2 + 1], key=lambda r: abs(r["offset"]))
    yours = next((r for r in rows if r["yours"]), None)
    near = sum(1 for r in rows if r["fits"] >= best - 1) / len(rows)  # share of the times searched that fit about as well
    at_best = sum(1 for r in rows if r["fits"] == best) / len(rows)
    narrowing = not wide or (best >= 2 and at_best <= 0.5 and near <= 0.6)
    # How strong is the test? Chance level at the middle time, and how many Mahadashas the events fall in.
    mc = mid["chart"]
    expected = sum(_base_rate(mc, KINDS[e["kind"]][1], birth, today) for e in events)

    def maha(d: date) -> str | None:
        iso = datetime.combine(d, dtime(12)).isoformat()
        return next((x["lord"] for x in mc["dasha"] if x["start"][:19] <= iso < x["end"][:19]), None)
    mahas = sorted({x for x in (maha(date.fromisoformat(e["date"])) for e in events) if x})
    n = len(events)
    dated = sum(1 for e in events if e["precision"] in ("day", "month"))
    if n < 6 or len(mahas) < 2 or not narrowing or (wide and dated < 4):
        strength = "weak"
    elif best - expected >= 2 and n >= 8:
        strength = "good"
    else:
        strength = "some"
    fmt = lambda t: datetime.strptime(t, "%H:%M").strftime("%-I:%M %p")
    same = yours and yours["fits"] == best and yours in run
    if wide and not narrowing:
        text = (f"Your events fit {best} of {n} at best, but about as well across much of the time searched "
                f"({round(near * 100)}% of times fit within one of the best), so they can't narrow your birth time.")
    else:
        text = (f"Your saved time, {fmt(request['tob'][:5])}, is already among the best fits ({best} of {n})." if same else
                f"Your events fit best between {fmt(run[0]['tob'])} and {fmt(run[-1]['tob'])} ({best} of {n})"
                + (f", against {yours['fits']} at your saved time." if yours else "."))
    others = [x for x in runs if x is not run]
    if others and narrowing:
        text += " Also " + str(best) + " of " + str(n) + " at " + ", ".join(
            fmt(x[0]["tob"]) + ("" if len(x) == 1 else "–" + fmt(x[-1]["tob"])) for x in others) + "."
    note = {"weak": ("This is only a hint, and it does not narrow your birth time. Events that fit much of the day "
                     "say little about the hour. Add events with their month, from different periods of your life."
                     if wide and not narrowing else
                     f"This is only a hint. All your events fall in your {mahas[0]} period" if len(mahas) == 1 else
                     f"This is only a hint. You have {n} events") +
                    ("" if wide and not narrowing else
                     f", and about {expected:.0f} of {n} would fit by chance. Add events from earlier periods "
                     "(school, a degree, a move, an illness) to make the rectification meaningful."),
            "some": f"A useful hint: your events span {len(mahas)} periods, but about {expected:.0f} of {n} "
                    "would fit by chance. More events make it firmer.",
            "good": f"A good sign: your events span {len(mahas)} periods and fit well above chance "
                    f"(about {expected:.0f} of {n} by chance)."}[strength]
    for r in rows:
        del r["chart"]
    windows = [{"from": x[0]["tob"], "to": x[-1]["tob"], "fits": best, "minutes": len(x) * step_min,
                "lagna": list(dict.fromkeys(r["lagna"] for r in x))}
               for x in sorted(runs, key=lambda x: (-len(x), x[0]["tob"]))[:6]]
    suggest = None if same or not narrowing else mid["tob"]
    return {"rows": rows, "best": best, "events": n, "expected": round(expected, 1), "strength": strength,
            "window": [run[0]["tob"], run[-1]["tob"]], "suggest": suggest, "mahadashas": mahas,
            "text": text, "note": note, "step": step_min, "ayanamsha": request.get("ayanamsha", "krishnamurti"),
            "scope": "day" if wide else "hour", "windows": windows, "near_best": round(near, 2),
            "narrowing": narrowing, "unknown": unknown,
            "labels": [f"{KINDS[e['kind']][0]} ({e['date'][:4]})" for e in events]}


def for_sukh(events: list[dict]) -> list[str]:
    return [f"{e['date'][:{'day': 10, 'month': 7, 'year': 4}[e['precision']]]}: {KINDS[e['kind']][0]}" for e in events]
