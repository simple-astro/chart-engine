"""Plain-language timing for the "Just guide me" level: the year ahead by area, and goal plans.

Both read KP timing (core/kp_predict.py) and say it without astrology words: no Dasha names, no houses.
- ``year_ahead``: the next 12 months for work, money, love and health as stretches (best, good, steady, slow,
  take care), merged where the tone stays the same.
- ``plan``: a goal (moving abroad, a new job…) with practical steps and the best stretch to act in. The steps are
  real-world actions; the chart only says when to push.
"""
from __future__ import annotations

from datetime import date

from core import kp_predict

# area -> (KP topic, label). Health reads the illness risk, so a strong window there means "take care".
AREAS = {"work": ("career", "Work"), "money": ("money", "Money"), "love": ("love", "Love"), "health": ("illness", "Health")}
TONE = {"event": {"strong": "best", "favourable": "good", "mixed": "steady", "challenging": "slow"},
        "risk": {"strong": "care", "favourable": "care", "mixed": "steady", "challenging": "good"}}
SAY = {
    "work": {"best": "Your strongest time for work. Apply, ask for more, start the big project.",
             "good": "Good, steady progress at work.",
             "steady": "Work moves at a normal pace. Keep at it.",
             "slow": "Work may feel slow. Learn and prepare; avoid big changes."},
    "money": {"best": "Best time for money. Savings grow and deals go well.",
              "good": "Money comes in steadily.",
              "steady": "Money stays about the same. Stick to your budget.",
              "slow": "Money is tight. Avoid big spending and lending."},
    "love": {"best": "A warm time for love. Good for proposals and big talks.",
             "good": "Relationships feel easy.",
             "steady": "Nothing big in love. Stay in touch and be kind.",
             "slow": "Go gently with loved ones; small things may hurt."},
    "health": {"care": "Look after your health: sleep, good food and a check-up.",
               "good": "A healthy stretch.",
               "steady": "Health is steady. Keep your routine."},
}


def _stretches(windows: list[dict], kind: str, start: str, end: str, top: float | None = None) -> list[dict]:
    """Windows as plain stretches. For events only the top-scoring strong windows (``top``, as ``best_stretch``
    reads them) are "best"; other strong ones are "good", so My year and My plans agree on the best time."""
    out: list[dict] = []
    for w in sorted(windows, key=lambda w: w["starts"]):
        a, b = max(w["starts"], start), min(w["ends"], end)
        if a >= b:
            continue
        tone = TONE[kind].get(w["verdict"], "steady")
        if tone == "best" and top is not None and w.get("score", 0) < top - 0.25:
            tone = "good"
        if out and out[-1]["tone"] == tone and out[-1]["ends"] >= a:
            out[-1]["ends"] = max(out[-1]["ends"], b)
        else:
            if out and out[-1]["ends"] < a:          # a gap between windows reads as an ordinary stretch
                out.append({"starts": out[-1]["ends"], "ends": a, "tone": "steady"})
            out.append({"starts": a, "ends": b, "tone": tone})
    return out


def year_ahead(chart: dict, today: date | None = None) -> dict:
    today = today or date.today()
    start, end = today.isoformat(), today.replace(year=today.year + 1).isoformat()
    areas = {}
    for key, (topic, label) in AREAS.items():
        p = kp_predict.predict(chart, topic, months=24)  # two years, so "best" is judged as the plans judge it
        kind = kp_predict.TOPICS[topic][-1]
        strong = [w.get("score", 0) for w in p.get("windows") or [] if w["ends"] > start and w["verdict"] == "strong"]
        st = _stretches(p.get("windows") or [], kind, start, end, max(strong) if strong and kind == "event" else None)
        for s in st:
            s["text"] = SAY[key].get(s["tone"]) or SAY[key]["steady"]
        areas[key] = {"label": label, "stretches": st}
    # "All": the stretches worth knowing about (best and take care), same dates joined across areas
    keyed: dict[tuple, dict] = {}
    for key, a in areas.items():
        for s in a["stretches"]:
            if s["tone"] in ("best", "care"):
                k = (s["starts"], s["ends"], s["tone"])
                keyed.setdefault(k, {**s, "areas": [], "text": s["text"]})["areas"].append(a["label"])
    highlights = sorted(keyed.values(), key=lambda s: s["starts"])
    return {"from": start, "to": end, "areas": areas, "highlights": highlights}


# ----- goal plans: practical steps; the chart adds the best stretch to act in -----
GOALS = {
    "abroad": {"title": "Moving abroad", "topic": "foreign", "steps": [
        ("route", "Find the visa or PR route that fits you, on the official government website"),
        ("eca", "Get your education assessed (for Canada, an ECA)"),
        ("lang", "Book and prepare for the language test"),
        ("police", "Get your police certificates"),
        ("funds", "Save and document your proof of funds"),
        ("letters", "Collect work reference letters")],
        "source": "Rules change often: follow the official immigration website, or a licensed consultant."},
    "job": {"title": "A new job", "topic": "career", "steps": [
        ("cv", "Update your CV and online profile"),
        ("list", "List 20 places you would like to work"),
        ("apply", "Send three applications a week"),
        ("refer", "Ask three people you know for a referral"),
        ("practice", "Practise interview answers out loud")]},
    "business": {"title": "Starting a business", "topic": "business", "steps": [
        ("plan", "Write a one-page plan: who buys, what, and why"),
        ("talk", "Talk to five possible customers"),
        ("rules", "Check registration, licences and taxes"),
        ("save", "Keep six months of costs aside"),
        ("first", "Launch a small first offer")]},
    "marriage": {"title": "Getting married", "topic": "marriage", "steps": [
        ("know", "Write down what matters to you in a partner"),
        ("family", "Talk with your family about what you want"),
        ("profile", "Make your profile or biodata"),
        ("meet", "Meet people, without rushing"),
        ("match", "Check your match with SimpleJyotish match making")]},
    "home": {"title": "Buying a home", "topic": "property", "steps": [
        ("credit", "Check your credit score"),
        ("down", "Save for the down payment"),
        ("approve", "Get a mortgage pre-approval"),
        ("areas", "Choose three areas you like"),
        ("inspect", "Book a home inspection before you sign")]},
    "exam": {"title": "Passing an exam", "topic": "exams", "steps": [
        ("syllabus", "Get the syllabus and past papers"),
        ("plan", "Make a daily study plan you can keep"),
        ("mock", "Take one mock test every week"),
        ("weak", "Spend extra time on your weak topics"),
        ("sleep", "Sleep at the same time every night")]},
    "savings": {"title": "Saving money", "topic": "money", "steps": [
        ("track", "Write down every expense for one month"),
        ("auto", "Set an amount to save on payday"),
        ("buffer", "Build three months of costs as a safety fund"),
        ("debt", "Pay off the costliest debt first"),
        ("subs", "Cancel subscriptions you do not use")]},
}
_STRENGTH = {"strong": 0, "favourable": 1}


def best_stretch(chart: dict, topic: str, today: date | None = None) -> dict | None:
    """The first run of the highest-scoring strong (else favourable) windows in the next two years that has not
    ended. Many charts have strong windows back to back for years, so only the top-scoring ones count."""
    t = (today or date.today()).isoformat()
    p = kp_predict.predict(chart, topic, months=24)
    live = [w for w in p.get("windows") or [] if w["ends"] > t and w["verdict"] in _STRENGTH]
    if not live:
        return None
    kind = min((w["verdict"] for w in live), key=_STRENGTH.get)
    pool = sorted((w for w in live if w["verdict"] == kind), key=lambda w: w["starts"])
    top = max(w.get("score", 0) for w in pool)
    run = [w for w in pool if w.get("score", 0) >= top - 0.25]
    a, b = max(run[0]["starts"], t), run[0]["ends"]
    for w in run[1:]:                                 # join back-to-back top windows
        if w["starts"] > b:
            break
        b = max(b, w["ends"])
    return {"starts": a, "ends": b, "strength": kind}


def plan(chart: dict, goal: str, done: set[str], today: date | None = None) -> dict:
    g = GOALS[goal]
    promise = (kp_predict.predict(chart, g["topic"], months=1).get("promise") or {}).get("verdict")
    return {"goal": goal, "title": g["title"], "source": g.get("source"),
            "steps": [{"id": sid, "text": text, "done": sid in done} for sid, text in g["steps"]],
            "best": best_stretch(chart, g["topic"], today),
            "effort": promise not in ("promised", "promised with obstacles")}  # say "may take more effort", never "no"
