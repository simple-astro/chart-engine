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

# kind: (what the person sees, the life matter it tests)
KINDS = {
    "married": ("Got married", "marriage"),
    "engaged": ("Got engaged", "marriage"),
    "child": ("Child born", "children"),
    "job": ("Started a job", "career"),
    "promotion": ("Promotion or raise", "career"),
    "job_change": ("Changed job", "job_change"),
    "job_loss": ("Lost a job or business loss", "career_loss"),
    "business": ("Started a business", "business"),
    "home": ("Bought a home or property", "property"),
    "sold": ("Sold a property", "property_sale"),
    "vehicle": ("Bought a vehicle", "vehicle"),
    "moved": ("Moved house", "residence"),
    "abroad": ("Moved or went abroad", "foreign"),
    "degree": ("Degree or exam passed", "education"),
    "award": ("Award or recognition", "awards"),
    "court_win": ("Won a court case", "litigation_win"),
    "illness": ("Illness or surgery", "illness"),
    "accident": ("Accident or injury", "accident"),
    "separation": ("Separation or divorce", "divorce"),
}
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
        risk = K.TOPICS[topic][6] == "risk"
        what = K.TOPICS[topic][0].lower()
        verb = "point" if len(helpers) > 1 else "points"
        if not helpers:
            why = f"{period} period: none of these lords is strong enough for {what}" + _held_back(at)
        elif at["verdict"] in GOOD:
            why = f"{period} period: {', '.join(helpers)} {verb} to {what}" + (
                " — your chart showed a time to take care" if risk else "")
        else:
            why = f"{period} period: only {', '.join(helpers)} {verb} to {what}, not enough on its own"
    return {"topic": topic, "fit": fit, "share": round(share, 2), "period": at and "–".join([at["maha"], at["antar"], at["praty"]]),
            "why": why, "rough": precision == "year"}


def summary(chart: dict, events: list[dict], birth: date, today: date) -> dict | None:
    """How many events the chart explains, against how many chance would explain."""
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


def for_sukh(events: list[dict]) -> list[str]:
    return [f"{e['date'][:{'day': 10, 'month': 7, 'year': 4}[e['precision']]]}: {KINDS[e['kind']][0]}" for e in events]
