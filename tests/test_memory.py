"""Memory: life events mentioned in chat are suggested, never saved, and only when worth an AI call."""
from datetime import date
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import chat, memory, storage
from app.main import app

REQ = {"name": "t", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}
TODAY = date(2026, 10, 20)


class FakeClient:
    def __init__(self, reply):
        self.calls, self.reply = [], reply
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return NS(content=[NS(type="text", text=self.reply)], usage=NS(input_tokens=400, output_tokens=40))


@pytest.mark.parametrize("msg,ok", [
    ("I changed my job in March 2024, what does my chart say?", True),
    ("We got married in 2016 and my son was born last year", True),
    ("I had surgery two years ago and still feel weak", True),
    ("When will I get married?", False),                       # no time cue, no past
    ("Will I change my job next year?", False),               # future
    ("What is my lagna?", False),
    ("ok", False),
])
def test_prefilter(msg, ok):
    assert memory.worth_asking(msg) is ok


def test_clean_keeps_only_real_new_events():
    raw = [{"kind": "job_change", "year": 2024, "month": 3}, {"kind": "nonsense", "year": 2020},
           {"kind": "married", "year": 2016, "month": 13},          # bad month: kept as year only
           {"kind": "child", "year": 2030},                         # future
           {"kind": "home", "year": 1980},                          # before birth
           {"kind": "job_change", "year": 2024, "month": 3},        # duplicate in the same reply
           {"kind": "moved", "year": 2019, "month": 5}]
    have = [{"kind": "moved", "date": "2019-05-01", "precision": "month"}]
    out = memory.clean(raw, date(1987, 9, 1), TODAY, have)
    assert [(e["kind"], e["year"], e["month"]) for e in out] == [("job_change", 2024, 3), ("married", 2016, None)]
    assert out[0]["when"] == "Mar 2024" and out[1]["when"] == "2016" and not out[0]["sensitive"]
    assert memory.clean([{"kind": "loss", "year": 2020}], date(1987, 9, 1), TODAY, [])[0]["sensitive"]


def _profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    return c, c.post("/profiles", json=REQ).json()["id"]


def test_suggest_calls_the_ai_only_for_worthy_messages_and_logs_it(tmp_path, monkeypatch):
    c, pid = _profile(tmp_path, monkeypatch)
    fake = FakeClient('{"events": [{"kind": "job_change", "year": 2024, "month": 3, "day": null}]}')
    monkeypatch.setattr(chat, "_client", lambda: fake)
    r = c.post(f"/profiles/{pid}/events/suggest", json={"message": "When will I get married?"})
    assert r.json() == {"suggestions": []} and fake.calls == []                          # never reached the AI
    r = c.post(f"/profiles/{pid}/events/suggest", json={"message": "I changed jobs in March 2024, how is my year?"})
    sug = r.json()["suggestions"]
    assert [(s["kind"], s["when"]) for s in sug] == [("job_change", "Mar 2024")] and len(fake.calls) == 1
    assert "TODAY:" in fake.calls[0]["messages"][0]["content"]
    assert storage.event_list(pid) == []                                                  # suggested, never saved
    assert storage.token_totals(False, ("memory",))[0]["inp"] == 400                      # the cost is recorded
    assert all(q["kind"] != "memory" for q in storage.recent_queries())                   # but not in the question log


def test_suggestion_is_dropped_once_the_event_is_saved(tmp_path, monkeypatch):
    c, pid = _profile(tmp_path, monkeypatch)
    monkeypatch.setattr(chat, "_client", lambda: FakeClient('{"events": [{"kind": "job_change", "year": 2024, "month": 3}]}'))
    msg = {"message": "I changed jobs in March 2024, how is my year?"}
    assert len(c.post(f"/profiles/{pid}/events/suggest", json=msg).json()["suggestions"]) == 1
    c.post(f"/profiles/{pid}/events", json={"kind": "job_change", "year": 2024, "month": 3})
    assert c.post(f"/profiles/{pid}/events/suggest", json=msg).json()["suggestions"] == []


def test_no_key_or_a_failing_call_gives_no_suggestions_and_no_error(tmp_path, monkeypatch):
    c, pid = _profile(tmp_path, monkeypatch)

    def boom():
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    monkeypatch.setattr(chat, "_client", boom)
    r = c.post(f"/profiles/{pid}/events/suggest", json={"message": "I changed jobs in March 2024, how is my year?"})
    assert r.status_code == 200 and r.json() == {"suggestions": []}


def test_daily_cap(tmp_path, monkeypatch):
    c, pid = _profile(tmp_path, monkeypatch)
    fake = FakeClient('{"events": []}')
    monkeypatch.setattr(chat, "_client", lambda: fake)
    monkeypatch.setattr(memory, "DAILY_CAP", 2)
    for _ in range(4):
        c.post(f"/profiles/{pid}/events/suggest", json={"message": "I changed jobs in March 2024, how is my year?"})
    assert len(fake.calls) == 2


def test_someone_elses_chart_is_not_reachable(tmp_path, monkeypatch):
    c, pid = _profile(tmp_path, monkeypatch)
    assert c.post("/profiles/999/events/suggest", json={"message": "I married in 2016"}).status_code == 404
