"""The Life Book: a personal book from the person's chart, steered by a few questions they answer first.

Flow: the person answers six short steps (focus, where they are in life, up to three questions, big life dates,
how each area feels now, preferences) → the book is written in the background → the astrologer reviews it in
Admin, adds notes and approves → only then the person can read it (status: writing → review → ready, or failed).

Every chapter except one is built by rules from the chart, so it holds no invented facts: strengths, house lords
(core/lord_placements.py), watch-outs, windows for the chosen areas (KP verdicts), the year ahead, a life balance
page (their own ratings beside what the chart shows now) and how well the chart fits the dates they gave. Only
"Your questions answered" is written by the AI, through the same fact-checked answer the chat uses
(chat.answer_once: up to three rewrites until it agrees with the chart). The book is stored as chapters made of a
few block types (p, list, cards, rows, qa) that the app shows one chapter per page.
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from app import storage

log = logging.getLogger(__name__)

# Areas the person can focus on: label, the KP matter for its timing (None: no timing chapter for it)
FOCUS = {
    "career": ("Career", "career"), "money": ("Money", "money"), "marriage": ("Marriage & relationships", "marriage"),
    "children": ("Children", "children"), "home": ("Home & property", "property"), "abroad": ("Living abroad", "foreign"),
    "studies": ("Studies", "education"), "health": ("Health habits", None), "spiritual": ("Spiritual path", None),
}
WORK = {"student": "a student", "job": "working in a job", "business": "running a business", "home": "a homemaker",
        "retired": "retired"}
RELATIONSHIP = {"single": "single", "relationship": "in a relationship", "married": "married"}
CHILDREN = {"none": "no children", "planning": "planning children", "yes": "have children"}
RATINGS = {"career": "Career", "money": "Money", "relationships": "Relationships", "health": "Health", "peace": "Peace of mind"}
TONE_WORDS = {"best": "A strong time", "good": "Good", "steady": "Steady", "slow": "Slow for now", "care": "Take care"}
STATUS_TEXT = {"writing": "Writing your book", "review": "Being reviewed by your astrologer", "ready": "Ready",
               "failed": "Something went wrong"}
DAILY_LIMIT = 3  # books a person can start in a day (each answers up to three questions with the AI)


def _ord(n: int) -> str:
    from core.lord_placements import ordinal
    return ordinal(n)


def _month(iso: str) -> str:
    return date.fromisoformat(iso[:10]).strftime("%b %Y")


def _span(a: str, b: str) -> str:
    return f"{_month(a)} – {_month(b)}"


def about(answers: dict) -> str:
    """What the person told us about their life, in one line (also given to the AI with each question)."""
    s = answers.get("stage") or {}
    bits = [WORK.get(s.get("work")), RELATIONSHIP.get(s.get("relationship")), CHILDREN.get(s.get("children"))]
    return ", ".join(b for b in bits if b)


def build(profile: dict, answers: dict, today: date | None = None) -> dict:
    """Every rules chapter of the book (no AI). "Your questions answered" is added by write()."""
    from app import goals
    from app import life_events as L
    from core import kp_predict, lord_placements
    from core.dignity import dignity
    today = today or date.today()
    chart, req = profile["chart"], profile["request"]
    first = (profile.get("name") or req.get("name") or "").split(" ")[0] or "You"
    g, lagna = chart["grahas"], chart["lagna"]
    lords = lord_placements.for_chart(chart, datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc))
    focus = [f for f in answers.get("focus") or [] if f in FOCUS][:3] or ["career", "money", "marriage"]
    married = (answers.get("stage") or {}).get("relationship") == "married"
    running = (chart.get("yoga_check") or {}).get("running") or {}
    chapters = []

    # 1. You at a glance
    glance = [["Lagna", f"{lagna['sign']} {int(lagna['ascendant'] % 30)}°"],
              ["Moon", f"{g['Moon']['sign']} · {g['Moon']['nakshatra']} pada {g['Moon']['pada']}"],
              ["Running now", " › ".join(running[k] for k in ("Mahadasha", "Antardasha") if running.get(k)) or "–"],
              ["Your focus", ", ".join(FOCUS[f][0] for f in focus)]]
    if about(answers):
        glance.append(["Where you are", about(answers).capitalize()])
    strong = [c for c in lords["cards"] if c["tag"] == "Strong"]
    care = [c for c in lords["cards"] if c["tag"] == "Needs care"]
    chapters.append({"key": "glance", "title": "You at a glance",
                     "intro": f"{first}, this book reads your birth chart for the parts of life you chose. Each "
                              "chapter names the chart fact behind what it says.",
                     "blocks": [{"type": "rows", "rows": glance},
                                {"type": "list", "title": "What stands out", "items": [h["t"] for h in lords["highlights"]]}]})

    # 2. Your strengths: Strong house lords, strong good yogas, planets in their best signs
    yogas = [y for y in (chart.get("yoga_check") or {}).get("yogas", []) if y.get("kind") == "good" and y.get("status") in ("Strong", "Mixed")]
    best = [p for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
            if dignity(p, g[p]["sign_index"]) in ("exalted", "own")]
    chapters.append({"key": "strengths", "title": "Your strengths",
                     "intro": "What your chart gives you to build on.",
                     "blocks": [{"type": "cards", "items": [{"title": f"{_ord(c['house'])} lord {c['lord']} in your {_ord(c['sits_in'])} house",
                                                             "tag": c["tag"], "text": c["text"]} for c in strong]},
                                {"type": "list", "title": "Yogas working for you",
                                 "items": [f"{y['name']}: {y['meaning']}" for y in yogas[:6]]},
                                {"type": "list", "title": "Planets in their best signs",
                                 "items": [f"{p} in {g[p]['sign']} ({dignity(p, g[p]['sign_index'])})" for p in best]}]})

    # 3. Your house lords: all twelve
    chapters.append({"key": "lords", "title": "Your house lords",
                     "intro": "Each house is run by its lord; where that lord sits shows where the house’s matters play out.",
                     "blocks": [{"type": "cards", "items": [{"title": f"{_ord(c['house'])} lord {c['lord']} in your {_ord(c['sits_in'])} house",
                                                             "tag": c["tag"], "text": c["text"], "sub": c["when"]} for c in lords["cards"]]}]})

    # 4. Watch-outs, each with a habit
    from app.guidance import REMEDY
    watch = [{"title": f"{_ord(c['house'])} lord {c['lord']} in your {_ord(c['sits_in'])} house", "tag": c["tag"],
              "text": c["text"], "sub": "A habit that helps: " + REMEDY[c["lord"]]} for c in care]
    for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        nb = ((chart.get("strength") or {}).get("neecha_bhanga") or {}).get(p) or {}
        if dignity(p, g[p]["sign_index"]) == "debilitated" and not nb.get("cancelled") and p not in {c["lord"] for c in care}:
            watch.append({"title": f"{p} is weak in {g[p]['sign']}", "tag": "Needs care",
                          "text": "Its matters ask for more patience and effort.", "sub": "A habit that helps: " + REMEDY[p]})
    if (answers.get("prefs") or {}).get("remedies") == "none":
        for w in watch:
            w.pop("sub", None)
    chapters.append({"key": "watch", "title": "Watch-outs",
                     "intro": "Areas to handle mindfully. None of them is fixed: each eases with time and good habits.",
                     "blocks": [{"type": "cards", "items": watch}] if watch else
                               [{"type": "p", "text": "No house lord in your chart is graded Needs care. Keep your strengths in use."}]})

    # 5. Your windows: the chosen areas over the next two years
    rows = []
    for f in focus:
        label, topic = FOCUS[f]
        if f == "marriage" and married:
            topic, label = "love", "Your relationship"
        if not topic:
            continue
        promise = (kp_predict.predict(chart, topic, months=1).get("promise") or {}).get("verdict") or "–"
        b = goals.best_stretch(chart, topic, today)
        rows.append([label, (f"Best stretch: {_span(b['starts'], b['ends'])} ({b['strength']})" if b else
                             "No standout window in the next two years: steady effort counts most")
                     + f" · KP promise: {promise}"])
    chapters.append({"key": "windows", "title": "Your windows",
                     "intro": "The best stretches in the next two years for the areas you chose, from the KP method. "
                              "A window is a good time to act, not a guarantee.",
                     "blocks": [{"type": "rows", "rows": rows}] if rows else
                               [{"type": "p", "text": "The areas you chose are read through your house lords and habits rather than dated windows."}]})

    # 6. The year ahead
    ya = goals.year_ahead(chart, today)
    chapters.append({"key": "year", "title": "The year ahead",
                     "intro": f"From {_month(ya['from'])} to {_month(ya['to'])}: the stretches worth knowing about.",
                     "blocks": [{"type": "list", "items": [f"{_span(h['starts'], h['ends'])} · {', '.join(h['areas'])}: {h['text']}"
                                                           for h in ya["highlights"]] or ["A steady year: no big highs or lows stand out."]}]})

    # 7. Life balance: their own ratings beside the chart now
    now_tone = {}
    for key, area in (("career", "work"), ("money", "money"), ("relationships", "love"), ("health", "health")):
        st = next((s for s in ya["areas"].get(area, {}).get("stretches", []) if s["starts"] <= today.isoformat() < s["ends"]), None)
        now_tone[key] = TONE_WORDS.get(st["tone"], "Steady") if st else "Steady"
    four = next(c for c in lords["cards"] if c["house"] == 4)
    now_tone["peace"] = {"Strong": "Well supported", "Mixed": "Mixed", "Needs care": "Needs care"}[four["tag"]] + " (your 4th lord)"
    ratings = answers.get("ratings") or {}
    chapters.append({"key": "balance", "title": "Life balance",
                     "intro": "How you said each area feels, beside what your chart shows now. Where they differ, the "
                              "chart’s timing often explains why, or shows what is coming.",
                     "blocks": [{"type": "rows", "rows": [[RATINGS[k], f"You: {ratings[k]}/5 · Chart now: {now_tone[k]}"
                                                           if isinstance(ratings.get(k), int) else f"Chart now: {now_tone[k]}"]
                                                          for k in RATINGS]}]})

    # 8. How your chart fits your life
    events = storage.event_list(profile["id"]) if profile.get("id") else []
    if events:
        birth = date.fromisoformat(req["dob"])
        checked = [{**e, "check": L.check(chart, e["kind"], date.fromisoformat(e["date"]), e["precision"])} for e in events]
        summ = L.summary(chart, checked, birth, today)
        fit = {"fits": "fits", "partly": "partly fits", "no": "does not fit", "noted": "noted"}
        chapters.append({"key": "fit", "title": "How your chart fits your life",
                         "intro": (summ or {}).get("text", "") + (" " + summ["note"] if summ and summ.get("note") else ""),
                         "blocks": [{"type": "rows", "rows": [[f"{L.KINDS[e['kind']][0]} ({e['date'][:7 if e['precision'] != 'year' else 4]})",
                                                               f"{fit[e['check']['fit']]}" + (f" · {e['check']['why']}" if e['check'].get('why') else '')]
                                                              for e in checked]}]})

    # 9. How it was calculated
    m = chart.get("meta") or {}
    ayan = {"krishnamurti": "KP (Krishnamurti)", "lahiri": "Lahiri", "raman": "Raman", "pushya": "Pushya-paksha",
            "fagan": "Fagan-Bradley"}.get(m.get("ayanamsha"), m.get("ayanamsha") or "Lahiri")
    chapters.append({"key": "method", "title": "How this book was made",
                     "blocks": [{"type": "list", "items": [
                         f"Positions from the Swiss Ephemeris; {ayan} ayanamsa; whole-sign houses from your lagna.",
                         "Strengths, house lords and watch-outs follow classical rules (Parashara), graded by your chart’s own dignity, combustion and aspects.",
                         "Windows use the KP method (cusp sub lords and the Vimshottari Dasha).",
                         "Your questions were answered by Astropositivism and checked against your chart before your astrologer reviewed them.",
                         "Tendencies, not certainties. Not medical, legal or financial advice."]}]})
    return {"title": f"{first}’s Life Book", "name": profile.get("name") or "", "made": today.isoformat(),
            "lagna": lagna["sign"], "chapters": chapters}


def write(profile: dict, answers: dict, book: dict) -> dict:
    """Adds "Your questions answered" (second chapter): each question answered by the fact-checked chat answer,
    with what the person told us about their life given as context."""
    from app import chat, config
    qs = [q.strip() for q in answers.get("questions") or [] if isinstance(q, str) and q.strip()][:3]
    if not qs:
        return book
    ctx = about(answers)
    items = []
    for q in qs:
        try:
            out = chat.answer_once(profile, q + (f" (About me: I am {ctx}.)" if ctx else ""), config.model())
            items.append({"q": q, "a": chat.limit_words(chat.drop_greeting(out["text"]), 250)})
        except Exception as e:  # the astrologer answers it in their notes instead
            log.warning("Life Book question failed: %r", e)
            items.append({"q": q, "a": "Your astrologer will answer this in their notes below."})
    book["chapters"].insert(1, {"key": "questions", "title": "Your questions answered",
                                "intro": "Answered from your chart and checked against it.",
                                "blocks": [{"type": "qa", "items": items}]})
    return book


def run(book_id: int) -> None:
    """Writes the book for a request and sends it to the astrologer's review (or marks it failed)."""
    b = storage.lifebook_get(book_id)
    p = b and storage.get(b["profile_id"])
    if not p:
        return
    try:
        from app import chat
        book = build(p, b["answers"], chat.local_today(p))
        book = write(p, b["answers"], book)
        storage.lifebook_update(book_id, status="review", book=book, error=None)
    except Exception as e:
        log.exception("Life Book %s failed", book_id)
        storage.lifebook_update(book_id, status="failed", error=repr(e)[:500])


def start(book_id: int) -> None:
    threading.Thread(target=run, args=(book_id,), daemon=True).start()


def view(b: dict | None, reviewer: bool = False) -> dict:
    """What the person (or the reviewer) sees: the status always; the book only once approved (or to the reviewer)."""
    if not b:
        return {"status": None}
    out = {"id": b["id"], "status": b["status"], "status_text": STATUS_TEXT.get(b["status"], b["status"]),
           "created_at": b["created_at"], "updated_at": b["updated_at"], "answers": b["answers"]}
    if b["status"] == "ready" or reviewer:
        book = dict(b["book"] or {})
        if book and b.get("notes"):
            chs = list(book.get("chapters", []))
            chs.insert(len(chs) - 1, {"key": "notes", "title": "Notes from your astrologer",
                                      "blocks": [{"type": "p", "text": b["notes"]}]})
            book["chapters"] = chs
        out["book"] = book or None
        out["notes"] = b.get("notes")
    if reviewer:
        out["error"] = b.get("error")
    return out
