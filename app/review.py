"""Studio Review (STUDIO_PLAN.md step 4): which answers astrologers check first, and what a review holds.

Queue, highest priority first; an answer leaves it once reviewed:
1. answers the fact check caught;
2. (later) answers users marked 👎, once 👍/👎 ships;
3. the first answer on a topic no one has reviewed yet;
4. a steady random 10% sample (the same answers stay sampled).
"""
from __future__ import annotations

from app.teach import topics_of

CHECKS = [("facts", "Chart facts correct"), ("method", "Method correct (KP / Nadi)"), ("timing", "Timing correct"),
          ("tone", "Tone: no fear"), ("action", "A useful action")]
TAGS = ["Wrong Dasha", "Wrong house", "Wrong date", "Fear word", "Too long", "Missed upaya", "Other"]
# Answers to remedy questions are checked for the remedy rules instead (STUDIO_PLAN.md, Remedies).
REMEDY_CHECKS = [("fits", "Fits this chart"), ("safe", "Safe"), ("habits", "Habits first"),
                 ("gems", "Gems only with a substitute and a consultation"), ("tone", "No fear and no japa")]
REMEDY_TAGS = ["Not for this chart", "Unsafe", "Japa suggested", "Gem without substitute", "Fear word", "Too long",
               "Other"]
RESULTS = ("pass", "fail", "na")
REASONS = {"caught": "The fact check caught something", "new_topic": "First answer on a topic not reviewed yet",
           "sample": "Random sample"}
_ORDER = {"caught": 0, "new_topic": 1, "sample": 2}


def _topics(question: str | None) -> list[str]:
    return topics_of(question or "") or ["Other"]


def check_set(question: str | None) -> tuple[str, list, list]:
    """("remedy", checks, tags) for a question about remedies, else ("reading", …)."""
    if "Remedies" in topics_of(question or ""):
        return "remedy", REMEDY_CHECKS, REMEDY_TAGS
    return "reading", CHECKS, TAGS


def sampled(usage_id: int) -> bool:
    """About 1 in 10 answers, chosen by id so the sample never shifts."""
    return (usage_id * 2654435761) % 100 < 10


def queue(rows: list[dict]) -> list[dict]:
    """rows: storage.review_candidates() (newest first). Unreviewed answers that need a look, in priority order,
    each with its reason and topics."""
    covered = {t for r in rows if r["review_id"] for t in _topics(r["question"])}
    first: dict[str, int] = {}
    for r in reversed(rows):  # oldest first: the first answer on each topic no one has reviewed
        if not r["review_id"]:
            for t in _topics(r["question"]):
                if t not in covered:
                    first.setdefault(t, r["id"])
    new_topic = set(first.values())
    out = []
    for r in rows:
        if r["review_id"]:
            continue
        fc = r.get("factcheck") or {}
        reason = ("caught" if fc.get("found") else "new_topic" if r["id"] in new_topic
                  else "sample" if sampled(r["id"]) else None)
        if reason:
            out.append({**r, "reason": reason, "reason_text": REASONS[reason], "topics": _topics(r["question"])})
    return sorted(out, key=lambda r: (_ORDER[r["reason"]], -r["id"]))


def clean(body: dict, question: str | None = None) -> tuple[dict, list[str], str | None]:
    """The checks, tags and note from a review form (the remedy checks for a remedy question); ValueError says
    what is missing."""
    _, check_list, tag_list = check_set(question)
    checks = body.get("checks") if isinstance(body.get("checks"), dict) else {}
    out = {}
    for key, name in check_list:
        if checks.get(key) not in RESULTS:
            raise ValueError(f"Mark “{name}” as pass, fail or not relevant")
        out[key] = checks[key]
    tags = body.get("tags") or []
    if not isinstance(tags, list) or any(t not in tag_list for t in tags):
        raise ValueError("Unknown problem tag")
    note = (body.get("note") or "").strip() or None
    if note and len(note) > 1000:
        raise ValueError("Keep the note under 1000 characters")
    if "fail" in out.values() and not tags and not note:
        raise ValueError("Add a problem tag or a note to say what went wrong")
    return out, list(dict.fromkeys(tags)), note
