"""Usage: which sections testers open and which they leave untouched (app/usage.py)."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import access, storage, usage
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield tmp_path / "p.db"
    access._fails.clear()


def _login(code, nxt=None):
    c = TestClient(app)
    data = {"code": code} | ({"next": nxt} if nxt else {})
    assert c.post("/login", data=data, follow_redirects=False).status_code == 303
    return c


def test_tester_events_show_in_the_report(gated):
    t = _login("tester-code")
    pid = t.post("/profiles", json=BODY).json()["id"]
    events = [{"name": "today"}, {"name": "timing/transits"}, {"name": "timing/transits"}, {"name": "kundli/yogas"},
              {"name": "find/open"}, {"name": "find/empty", "detail": "  transit chart  "},
              {"name": "find/pick", "detail": "dasha → Your periods now"},
              {"name": "made-up"}, {"name": "today", "detail": "ignored detail"}]
    assert t.post("/events", json={"events": events}).status_code == 204
    storage.log_usage(pid, "llm", "When will I get a job promotion?", owner=sqlite3.connect(gated).execute("SELECT owner FROM profiles WHERE id = ?", (pid,)).fetchone()[0])
    r = _login("admin-code", "/admin").get("/admin/api/usage").json()
    f = {x["key"]: x for x in r["features"]}
    assert f["timing/transits"]["week"] == {"opens": 2, "testers": 1}
    assert f["kundli/yogas"]["month"]["opens"] == 1 and f["asked"]["month"]["opens"] == 1
    assert "Lal Kitab" in r["untouched"] and "Transits" not in r["untouched"]
    assert r["searches"]["empty"] == [{"query": "transit chart", "count": 1}]
    assert r["searches"]["picked"][0]["search"] == "dasha → Your periods now"
    assert {t["topic"]: t["month"] for t in r["topics"]}["Career & job"] == 1
    assert r["journey"][0]["testers"] == 1 and r["journey"][2]["testers"] == 1
    [row] = r["testers"]
    assert row["tester"].startswith("Tester ") and "owner" not in row and row["questions"] == 1
    assert row["top"][0] == "Transits"
    rows = sqlite3.connect(gated).execute("SELECT name, detail FROM events").fetchall()
    assert ("made-up", None) not in rows and ("today", None) in rows and ("today", "ignored detail") not in rows


def test_admin_visits_are_not_recorded(gated):
    a = _login("admin-code", "/admin")
    assert a.post("/events", json={"events": [{"name": "today"}]}).status_code == 204
    assert sqlite3.connect(gated).execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    assert _login("tester-code").get("/admin/api/usage").status_code == 403
    assert _login("tester-code").post("/events", json={"events": "nope"}).status_code == 422


def test_events_older_than_90_days_are_removed(gated):
    t = _login("tester-code")
    t.post("/events", json={"events": [{"name": "today"}]})
    old = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat(timespec="seconds")
    con = sqlite3.connect(gated)
    con.execute("UPDATE events SET ts = ?", (old,)); con.commit()
    t.post("/events", json={"events": [{"name": "kundli"}]})
    assert [r[0] for r in con.execute("SELECT name FROM events")] == ["kundli"]


def test_question_topics():
    c = usage.topics(["Will I get PR in Canada?", "When should I marry?", "Which remedies suit me now?", "Hello"])
    assert c["Abroad & visa"] == 1 and c["Marriage & love"] == 1 and c["Remedies"] == 1 and c["Other"] == 1
    assert c["Timing & muhurat"] == 1      # "When should I marry?"


def test_every_tracked_name_is_in_the_catalogue():
    stored_only = usage.STORED
    assert usage.TRACKED - {"find/pick", "find/empty"} == set(usage.LABEL) - stored_only
