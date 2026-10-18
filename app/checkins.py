""""How did it go?": when someone asks about something with a date, ask them once, a couple of days after it.

A check-in is made from a question that names a day still ahead ("my interview on 20 Oct", "tomorrow", "on
Friday"), up to 90 days out. It falls due two days after that day and is shown once, on Today and on Telegram
for linked users. "Not yet" asks again three days later. The answers grow the real-life backtest, and a "went
well" can be added to Your life so far with that date.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from app import storage
from app.usage import topics

MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                          "nov", "dec"))}
MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DAY_MON = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MON + r"(?:,?\s+(\d{4}))?\b", re.I)
MON_DAY = re.compile(r"\b" + MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?", re.I)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAY = re.compile(r"\b(?:on|this|next|coming)\s+(" + "|".join(WEEKDAYS) + r")\b", re.I)
AFTER_DAYS, AGAIN_DAYS, HORIZON = 2, 3, 90
ANSWERS = {"well": "Went well", "mixed": "Mixed", "poor": "Didn't go well", "notyet": "Not yet"}
# The life event a "went well" can become, only when the question names that event itself (an interview going well
# is not "started a job"; a wrong event would spoil the chart-accuracy and birth-time checks). life_events.KINDS keys.
EVENT_WORDS = [
    ("married", r"\b(wedding|marriage ceremony|getting married|shaadi|vivah)\b"),
    ("engaged", r"\b(engagement|roka|sagai)\b"),
    ("job", r"\b(join\w*|joining date|start\w* (a |my |the )?(new )?job|job offer|offer letter)\b"),
    ("promotion", r"\b(promotion|appraisal|raise)\b"),
    ("business", r"\b(launch\w*|open\w*|start\w*) (my |a |the |our )?(business|shop|startup|store|clinic)\b"),
    ("home", r"\b(buy\w*|purchas\w*|registr\w*|possession)\b[^.?!]*\b(house|home|flat|property|land|plot)\b"),
    ("vehicle", r"\b(buy\w*|purchas\w*|deliver\w*)\b[^.?!]*\b(car|vehicle|bike|scooter)\b"),
    ("moved", r"\b(shift\w*|mov\w*) (to a |to my |into )?(new )?(house|home|flat)\b"),
    ("abroad", r"\b(visa|flight|fly\w*|move abroad|immigrat\w*)\b"),
    ("degree", r"\b(exam|result|degree|admission)\b"),
    ("child", r"\b(delivery|due date|baby (is )?due)\b"),
    ("court_win", r"\b(court|hearing|verdict|case)\b"),
]


def event_date(question: str, asked: date) -> date | None:
    """The first day named in the question that is still ahead (within HORIZON days), else None."""
    q = question or ""
    found: list[date] = []
    for m in DAY_MON.finditer(q):
        found.append(_mk(m.group(3), MONTHS[m.group(2).lower()[:3]], int(m.group(1)), asked))
    for m in MON_DAY.finditer(q):
        found.append(_mk(m.group(3), MONTHS[m.group(1).lower()[:3]], int(m.group(2)), asked))
    low = q.lower()
    if re.search(r"\bday after tomorrow\b", low):
        found.append(asked + timedelta(days=2))
    elif re.search(r"\btomorrow\b|\bkal\b", low):
        found.append(asked + timedelta(days=1))
    for m in WEEKDAY.finditer(q):
        ahead = (WEEKDAYS.index(m.group(1).lower()) - asked.weekday()) % 7 or 7
        found.append(asked + timedelta(days=ahead))  # "next Monday" is taken as the coming Monday
    ok = [d for d in found if d and asked < d <= asked + timedelta(days=HORIZON)]
    return min(ok) if ok else None


def _mk(year: str | None, month: int, day: int, asked: date) -> date | None:
    try:
        d = date(int(year) if year else asked.year, month, day)
    except ValueError:
        return None
    if not year and d < asked:  # "5 Jan" asked in December means next January
        try:
            d = date(asked.year + 1, month, day)
        except ValueError:
            return None
    return d


def _said(answer: str) -> str:
    """The answer's first sentence, plain, to remind them what we said."""
    text = re.sub(r"[*_#`>]", "", answer or "").strip()
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return first[:180]


def from_question(profile_id: int, usage_id: int, question: str, answer: str, asked: date) -> dict | None:
    """Make a check-in if the question names a day ahead; one per day per chart."""
    d = event_date(question, asked)
    if not d:
        return None
    t = [x for x in topics([question]) if x not in ("Other", "Timing & muhurat")]
    return storage.checkin_add(profile_id, usage_id, question[:300], _said(answer), d.isoformat(),
                               (d + timedelta(days=AFTER_DAYS)).isoformat(), t[0] if t else None)


def view(c: dict) -> dict:
    return {"id": c["id"], "question": c["question"], "said": c["said"], "event_date": c["event_date"],
            "topic": c["topic"], "event_kind": event_kind(c["question"])}


def event_kind(question: str) -> str | None:
    """The life event the question itself names, if any."""
    return next((k for k, rx in EVENT_WORDS if re.search(rx, question or "", re.I)), None)


def due(profile_id: int, today: date) -> dict | None:
    """The oldest check-in waiting for an answer today, if any."""
    c = storage.checkin_due(profile_id, today.isoformat())
    return view(c) if c else None


def answer(profile_id: int, checkin_id: int, key: str, today: date) -> bool:
    if key not in ANSWERS:
        return False
    if key == "notyet":
        return storage.checkin_snooze(profile_id, checkin_id, (today + timedelta(days=AGAIN_DAYS)).isoformat())
    return storage.checkin_answer(profile_id, checkin_id, key)
