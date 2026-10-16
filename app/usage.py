"""Which parts of the app testers use, and which they leave untouched — the Admin "Usage" section.

- Section events come from the page (POST /events): a short name such as "timing/transits" or "kundli/yogas",
  sent in small batches. No chart data and no question text; Find searches keep the words typed (80 characters).
- Actions come from what is already stored: questions to Astropositivism, mood logs, life events, Get-ready ticks, charts.
- Admin visits (and local single-user mode) are never recorded. Events are kept for 90 days (storage.EVENT_DAYS).
CATALOGUE is the full list of sections, so anything nobody opened shows up as untouched.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from app import storage

CATALOGUE = [
    ("Today", [("today", "Today screen"), ("today/muhurat", "Best and worst times"),
               ("mood", "How are you feeling? (logged)")]),
    ("Timing", [("timing/now", "Now & next"), ("timing/comingup", "Coming up"), ("timing/chara", "Chara Dasha"),
                ("getready", "Get-ready steps ticked"), ("timing/transits", "Transits"),
                ("timing/matter", "By matter (KP timing)"), ("timing/dates", "Good dates")]),
    ("Ask Astropositivism", [("ask", "Ask Astropositivism screen"), ("asked", "Questions asked")]),
    ("Remedies", [("remedies", "Remedies screen")]),
    ("Kundli", [("kundli", "Kundli screen"), ("links/place", "Placement arrows"), ("links/asp", "Aspect arrows"),
                ("links/conj", "Conjunctions"), ("house/tap", "Tap a house"), ("chart/chalit", "Bhava Chalit view"),
                ("chart/alul", "AL · UL on the chart"), ("kundli/planets", "Planets"), ("kundli/yogas", "Yogas"),
                ("kundli/houses", "Houses & cusps"), ("kundli/vargas", "Divisional charts"),
                ("kundli/akv", "Ashtakavarga"), ("kundli/nadi", "Nadi amsha"), ("kundli/xchg", "Lord exchange"),
                ("kundli/jaimini", "Jaimini"), ("kundli/bnn", "BNN"), ("kundli/lal", "Lal Kitab"),
                ("kundli/about", "About you"), ("lifeevents", "Life events added")]),
    ("Find", [("find/open", "Find opened")]),
]
LABEL = {k: label for _, items in CATALOGUE for k, label in items}
STORED = {"mood", "getready", "asked", "lifeevents"}            # counted from stored data, not page events
TRACKED = (set(LABEL) - STORED) | {"find/pick", "find/empty"}  # names the page may send
MAX_BATCH = 50

# Question topics: a question can count under more than one.
TOPICS = [
    ("Career & job", r"\b(job|career|promotion|work|office|boss|interview|salary|employ\w*)\b"),
    ("Business", r"\b(business|shop|startup|partnership|client\w*|customer\w*)\b"),
    ("Money", r"\b(money|wealth|financ\w*|income|debt|loan|invest\w*|saving\w*|rich|profit)\b"),
    ("Marriage & love", r"\b(marr\w*|wedding|spouse|husband|wife|love|relationship|girlfriend|boyfriend|partner)\b"),
    ("Health", r"\b(health|ill\w*|disease|sick|surgery|pain|sleep|stress|anxiety|energy)\b"),
    ("Abroad & visa", r"\b(abroad|foreign|visa|pr|permanent residency|immigra\w*|canada|usa|uk|australia|settle\w*|overseas)\b"),
    ("Children", r"\b(child\w*|son|daughter|pregnan\w*|baby|kids?)\b"),
    ("Education", r"\b(stud\w*|exam\w*|education|college|admission|course|degree)\b"),
    ("Property & home", r"\b(property|house|home|land|flat|vehicle|car)\b"),
    ("Remedies", r"\b(remed\w*|upaya|gem\w*|stone\w*|mantra|puja|donat\w*)\b"),
    ("Timing & muhurat", r"\b(when|today|tomorrow|muhurat|date|transit\w*|dasha|period|this (week|month|year))\b"),
]
_TOPICS = [(name, re.compile(rx, re.I)) for name, rx in TOPICS]

router = APIRouter(tags=["usage"])


@router.post("/events", status_code=204, include_in_schema=False)
async def events(request: Request) -> Response:
    """A batch of section events from the page. Unknown names are ignored; admin visits are not recorded."""
    if request.state.admin:
        return Response(status_code=204)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=422, detail="Expected JSON") from None
    items = body.get("events") if isinstance(body, dict) else None
    if not isinstance(items, list):
        raise HTTPException(status_code=422, detail="Expected a list of events")
    rows = []
    for it in items[:MAX_BATCH]:
        name = it.get("name") if isinstance(it, dict) else None
        if not isinstance(name, str) or name not in TRACKED:
            continue
        detail = it.get("detail")
        detail = detail.strip()[:80] if name.startswith("find/") and isinstance(detail, str) and detail.strip() else None
        rows.append((name, detail))
    if rows:
        storage.log_events(request.state.owner, rows)
    return Response(status_code=204)


def topics(questions: list[str]) -> Counter:
    out = Counter()
    for q in questions:
        hits = [name for name, rx in _TOPICS if rx.search(q or "")]
        out.update(hits or ["Other"])
    return out


def report(now: datetime | None = None) -> dict:
    """Feature map (7 and 30 days), untouched sections, Find searches, question topics, journey and per tester.
    Owners are returned raw; the admin route turns them into tester labels."""
    now = now or datetime.now(timezone.utc)
    iso = lambda d: (now - timedelta(days=d)).isoformat(timespec="seconds")
    src = storage.usage_sources(iso(30))
    hits = [(e["ts"], e["owner"], e["name"]) for e in src["events"]]
    for name in STORED:
        hits += [(r["ts"], r["owner"], name) for r in src[name if name != "asked" else "questions"]]

    def count(days: int) -> dict:
        since, opens, who = iso(days), Counter(), defaultdict(set)
        for ts, owner, name in hits:
            if ts >= since:
                opens[name] += 1
                who[name].add(owner)
        return {k: {"opens": opens[k], "testers": len(who[k])} for k in LABEL}

    week, month = count(7), count(30)
    features = [{"area": area, "key": k, "label": label, "week": week[k], "month": month[k]}
                for area, items in CATALOGUE for k, label in items]

    searches = [e for e in src["events"] if e["name"] in ("find/pick", "find/empty")]
    empty = Counter((e["detail"] or "").lower() for e in searches if e["name"] == "find/empty")
    picked = Counter(e["detail"] or "" for e in searches if e["name"] == "find/pick")

    qs = src["questions"]
    t7, t30 = topics([q["question"] for q in qs if q["ts"] >= iso(7)]), topics([q["question"] for q in qs])
    topic_rows = [{"topic": t, "week": t7[t], "month": t30[t]} for t in [n for n, _ in TOPICS] + ["Other"]]
    topic_rows.sort(key=lambda r: (-r["month"], -r["week"]))

    # Activity per tester over 30 days: every event, question, mood log, life event, tick and new chart.
    days, last, top, asked = defaultdict(set), {}, defaultdict(Counter), Counter()
    activity = hits + [(r["ts"], r["owner"], "chart") for r in src["charts"]]
    for ts, owner, name in activity:
        days[owner].add(ts[:10])
        last[owner] = max(last.get(owner, ""), ts)
        if name in LABEL and name not in ("today", "kundli", "ask", "remedies", "find/open"):
            top[owner][name] += 1                      # the screens themselves say little; sections do
        if name == "asked":
            asked[owner] += 1
    owners = set(days)
    with_chart = owners & set(src["chart_owners"])
    journey = [{"step": "Used the app", "testers": len(owners)},
               {"step": "Has a chart", "testers": len(with_chart)},
               {"step": "Asked Astropositivism", "testers": len(with_chart & set(asked))},
               {"step": "Came back on another day", "testers": len({o for o in with_chart & set(asked) if len(days[o]) > 1})}]
    testers = sorted(({"owner": o, "last_seen": last[o], "days_active": len(days[o]), "questions": asked[o],
                       "top": [LABEL[k] for k, _ in top[o].most_common(3)]} for o in owners),
                     key=lambda r: r["last_seen"], reverse=True)
    return {
        "tracking_since": src["tracking_since"],
        "active": {"week": len({o for ts, o, _ in activity if ts >= iso(7)}), "month": len(owners)},
        "features": features,
        "untouched": [f["label"] for f in features if not f["month"]["opens"]],
        "searches": {"empty": [{"query": q, "count": n} for q, n in empty.most_common(15) if q],
                     "picked": [{"search": q, "count": n} for q, n in picked.most_common(15) if q]},
        "topics": topic_rows,
        "journey": journey,
        "testers": testers,
    }
