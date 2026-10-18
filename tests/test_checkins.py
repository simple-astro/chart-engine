""""How did it go?": a question about a day ahead becomes one check-in, due two days after that day."""
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app import checkins, storage
from app.main import app

BODY = {"name": "T", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.61, "lon": 77.2, "tz_name": "Asia/Kolkata"}
WED = date(2026, 10, 14)


def test_finds_the_day_ahead():
    assert checkins.event_date("I have an interview on 20 Oct, how will it go?", WED) == date(2026, 10, 20)
    assert checkins.event_date("visa decision on November 3rd", WED) == date(2026, 11, 3)
    assert checkins.event_date("Is tomorrow good for signing?", WED) == date(2026, 10, 15)
    assert checkins.event_date("property deal next Monday", WED) == date(2026, 10, 19)
    assert checkins.event_date("What happened on 2 Oct?", WED) is None            # already past
    assert checkins.event_date("Will I marry in 2027?", WED) is None              # no day named
    assert checkins.event_date("my exam on 5 Jan", date(2026, 12, 20)) == date(2027, 1, 5)


def test_due_answer_snooze_and_add_as_life_event(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=BODY).json()["id"]
    ck = checkins.from_question(pid, 1, "Job interview on 20 Oct?", "**Yes** — the morning looks good. More text.", WED)
    assert ck["topic"] == "Career & job" and ck["due_date"] == "2026-10-22" and ck["said"] == "Yes — the morning looks good."
    assert checkins.from_question(pid, 2, "And the interview on 20 Oct again?", "x", WED) is None  # one per day
    assert checkins.due(pid, date(2026, 10, 21)) is None
    due = checkins.due(pid, date(2026, 10, 22))
    assert due["event_kind"] is None                      # an interview going well is not "started a job"
    assert checkins.event_kind("My joining date is 3 Nov, is it good?") == "job"
    assert checkins.event_kind("Visa interview on 5 Dec") == "abroad"
    assert checkins.event_kind("We are buying a flat on 12 Nov") == "home"
    assert checkins.answer(pid, due["id"], "notyet", date(2026, 10, 22))
    assert checkins.due(pid, date(2026, 10, 24)) is None and checkins.due(pid, date(2026, 10, 25))
    assert c.post(f"/profiles/{pid}/checkin/{due['id']}", json={"answer": "well"}).json()["ok"]
    assert checkins.due(pid, date(2026, 10, 30)) is None
    assert storage.checkin_counts("2000-01-01") == {"asked": 1, "well": 1}
    assert c.post(f"/profiles/{pid}/checkin/{due['id']}", json={"answer": "maybe"}).status_code == 422
