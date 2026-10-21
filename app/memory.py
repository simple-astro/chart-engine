"""Memory: life events people mention in chat, offered back as "Add this to Your life so far?".

Nothing is ever saved here. A suggestion becomes an event only when the person taps Add (the normal events
endpoint), because the events feed the accuracy checks and the real-life backtest: guessed events would poison both.

A message is only sent to the AI when it has both a life-event word and a time cue (a year, a month, "last year",
"ago"), so most chat messages cost nothing. The AI sees the message alone, picks from the fixed event kinds, and is
told to ignore plans, hypotheticals, other people's lives and anything without a time.
"""
from __future__ import annotations

import json
import re
from datetime import date

from app import config, life_events as L, storage

MODEL = "claude-haiku-4-5"
DAILY_CAP = 25  # suggestion calls per chart per day: a guard on cost, not a feature limit

_EVENT = re.compile(
    r"\b(married|marriage|wedding|engaged|engagement|divorc\w*|separat\w*|got together|love affair|"
    r"jobs?|joined|resign\w*|quit|fired|laid off|promot\w*|business|startup|started working|"
    r"bought|sold|moved|shifted|relocat\w*|houses?|flats?|propert\w*|cars?|vehicle|"
    r"son|daughter|baby|child|born|pregnan\w*|"
    r"surgery|operation|accident|injur\w*|ill|sick|hospital|cancer|"
    r"degree|graduat\w*|passed|exam|admission|college|school|"
    r"abroad|visa|migrat\w*|immigrat\w*|"
    r"passed away|died|death|lost my|"
    r"award|won|court|case|loan|debt|inherit\w*|pilgrimage|deeksha|initiat\w*)\b", re.I)
_MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|"
           "september|october|november|december")
_WHEN = re.compile(rf"\b((?:19|20)\d\d|{_MONTHS}|last year|last month|years? ago|months? ago|a year ago|ago|"
                   r"in my (?:teens|twenties|thirties|forties)|when i was \d+|at the age of \d+|age \d+)\b", re.I)
_PAST = re.compile(r"\b(i|we|my|he|she)\b.*\b(got|was|were|had|did|started|moved|joined|lost|bought|sold|left|"
                   r"passed|finished|completed|married|born|went|came|became|\w+ed)\b", re.I)

SENSITIVE = {"loss", "illness", "accident", "parent_illness", "separation", "job_loss", "money_loss"}

SYSTEM = (
    "You read one message a person sent to their astrologer and pick out PAST life events they say happened TO THEM "
    "or in their own family where the kind below fits. Rules: only events that already happened; ignore plans, "
    "wishes, questions about the future and hypotheticals; ignore other people's lives (a friend, a colleague, a "
    "celebrity); each event needs a year you can read or work out from today's date (for example 'last year', "
    "'three years ago'); give the month only if said; never guess. A parent's illness is kind parent_illness; a death "
    "in the family is kind loss. Return JSON only: "
    '{"events": [{"kind": "<key>", "year": 2024, "month": 3 or null, "day": null}]} and {"events": []} when none.')


def worth_asking(message: str) -> bool:
    """The cheap pre-filter: a life-event word, a time cue and some first-person past tense."""
    m = message or ""
    return len(m) >= 12 and bool(_EVENT.search(m) and _WHEN.search(m) and _PAST.search(m))


def _parse(text: str) -> list[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        got = json.loads(m.group(0)).get("events")
    except ValueError:
        return []
    return got if isinstance(got, list) else []


def _same(a: dict, kind: str, year: int, month: int | None) -> bool:
    """Is this suggestion already one of the person's events (same kind, same year, and same month if both say)?"""
    d = date.fromisoformat(a["date"])
    return (a["kind"] == kind and d.year == year
            and (month is None or a["precision"] == "year" or d.month == month))


def clean(raw: list[dict], birth: date, today: date, have: list[dict]) -> list[dict]:
    out, seen = [], []
    for e in raw[:4]:
        if not isinstance(e, dict) or e.get("kind") not in L.KINDS:
            continue
        try:
            year = int(e["year"])
            month = int(e["month"]) if e.get("month") not in (None, "", 0) else None
        except (TypeError, ValueError, KeyError):
            continue
        if month is not None and not 1 <= month <= 12:
            month = None
        try:
            d = date(year, month or 1, 1)
        except ValueError:
            continue
        if d < date(birth.year, birth.month if month else 1, 1) or d > today:
            continue
        key = (e["kind"], year, month)
        if key in seen or any(_same(a, *key) for a in have):
            continue
        seen.append(key)
        label = L.KINDS[e["kind"]][0]
        when = f"{date(year, month, 1):%b %Y}" if month else str(year)
        out.append({"kind": e["kind"], "label": label, "year": year, "month": month, "day": None,
                    "when": when, "sensitive": e["kind"] in SENSITIVE})
    return out


def _calls_today(pid: int) -> int:
    with storage._lock, storage._connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM usage_log WHERE kind = 'memory' AND profile_id = ? AND "
                            "substr(ts, 1, 10) = ?", (pid, storage._today())).fetchone()[0]


def suggest(profile: dict, message: str, today: date) -> list[dict]:
    """Candidate life events in the message (never saved); [] when none, or when the AI is unavailable."""
    if not worth_asking(message) or _calls_today(profile["id"]) >= DAILY_CAP:
        return []
    from app import chat
    kinds = "\n".join(f"{k}: {v[0]}" for k, v in L.KINDS.items())
    try:
        client = chat._client()
        resp = client.messages.create(
            model=MODEL, max_tokens=300, system=SYSTEM,
            messages=[{"role": "user", "content": f"TODAY: {today.isoformat()}\nKINDS:\n{kinds}\n\nMESSAGE:\n{message[:1500]}"}])
    except Exception:  # no key, or the call failed: suggestions are a nicety
        return []
    u = getattr(resp, "usage", None)
    storage.log_usage(profile["id"], "memory", message[:200], model=MODEL,
                      input_tokens=getattr(u, "input_tokens", 0) or 0, output_tokens=getattr(u, "output_tokens", 0) or 0,
                      cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                      cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0, owner=profile.get("owner"))
    raw = _parse("".join(getattr(b, "text", "") for b in resp.content))
    return clean(raw, date.fromisoformat(profile["request"]["dob"]), today, storage.event_list(profile["id"]))
