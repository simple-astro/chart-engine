"""KP prediction engine: promise, lord judgement, windows, routing, and the chat/guard wiring."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import factcheck as F, synthesis
from app.main import app
from core import kp_predict as K

BIRTH = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata"}
START = date(2026, 10, 8)


@pytest.fixture(scope="module")
def chart():
    return TestClient(app).post("/chart", json=BIRTH).json()


def test_career_uses_confirmed_houses_and_promise(chart):
    r = K.predict(chart, "career", START)
    assert r["houses_for"] == [2, 6, 10, 11] and r["houses_against"] == [5, 9]
    p = r["promise"]
    assert p["cusp_sub_lord"] == "Mercury" and p["verdict"] == "promised" and 10 in p["signifies"]


def test_lord_judgement_star_and_sub(chart):
    good, bad = {2, 6, 10, 11}, {5, 9}
    sun = K.judge_lord(chart, "Sun", good, bad)
    assert sun["sub_lord"] == "Venus" and sun["verdict"] == "supports"  # Venus signifies 6, 11 vs 9
    assert K.judge_lord(chart, "Mars", good, bad)["verdict"] == "blocks"  # gives 5, 8, 9, 12
    assert K.judge_lord(chart, "Ketu", good, bad)["verdict"] == "mixed"  # 10 and 9 balance out


def test_windows_cover_the_horizon(chart):
    r = K.predict(chart, "career", START, months=24)
    ws = r["windows"]
    assert ws[0]["starts"] <= START.isoformat() < ws[0]["ends"]
    assert all(a["ends"] == b["starts"] for a, b in zip(ws, ws[1:]))
    assert {w["verdict"] for w in ws} <= {"strong", "favourable", "mixed", "challenging"}
    by = {w["praty"]: w for w in ws}
    assert by["Venus"]["score"] > by["Mars"]["score"]  # supporting pratyantar beats a blocking one
    assert all(len(w["reasons"]) == 3 for w in ws)


def test_topic_routing():
    assert K.topics_for("When will I get a promotion at my job?") == ["career"]
    assert K.topics_for("Will I settle abroad after marriage?") == ["marriage", "foreign"]
    assert K.topics_for("What does my Moon mean?") == []


def test_brief_is_compact_and_complete(chart):
    b = K.brief(K.predict(chart, "career", START))
    assert "promised" in b and "2026-06-23 to 2026-11-16" in b and b.count("\n- ") >= 7
    assert len(b) < 3500


def test_unknown_topic(chart):
    with pytest.raises(ValueError):
        K.predict(chart, "lottery", START)


def test_guard_flags_a_window_rated_opposite(chart):
    kp = {"career": K.predict(chart, "career", START)}
    facts = F.facts_from(synthesis.build({"chart": chart, "request": BIRTH}, datetime(2026, 10, 8, tzinfo=timezone.utc)),
                         chart, kp=kp)
    strong = next(w for w in kp["career"]["windows"] if w["verdict"] == "strong")
    s, e = date.fromisoformat(strong["starts"]), date.fromisoformat(strong["ends"])
    bad = f"{s:%d %b %Y} to {e:%d %b %Y} is a difficult time for your career."
    good = f"{s:%d %b %Y} to {e:%d %b %Y} is a strong time for your career."
    assert any("called difficult" in i["claim"] for i in F.check(bad, facts))
    assert F.check(good, facts) == []


def test_chat_gets_brief_for_topic_questions_only(chart):
    from app import chat
    prof = {"chart": chart, "request": BIRTH, "id": 1}
    assert "KP PREDICTION — Career" in chat.kp_context(prof, "How is my career next year?")
    assert chat.kp_context(prof, "What does my Moon mean?") == ""


def test_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=BIRTH).json()["id"]
    r = c.get(f"/profiles/{pid}/kp/marriage?months=12").json()
    assert r["topic"] == "marriage" and r["windows"]
    assert c.get(f"/profiles/{pid}/kp/lottery").status_code == 422
