"""The "Just guide me" level: the year ahead in words, and goal plans (app/goals.py)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import chat, goals
from app.main import app
from app.routes import with_extras
from core.chart import BirthData, compute_natal_chart

BODY = {"name": "Asha", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "")
    return TestClient(app)


def _chart():
    return with_extras(compute_natal_chart(BirthData(name="A", dob=date(1987, 9, 1), tob=__import__("datetime").time(14, 20),
                                                     lat=30.7333, lon=76.7794, tz_name="Asia/Kolkata")))


def test_year_ahead_covers_the_year_in_plain_words():
    y = goals.year_ahead(_chart(), date(2026, 10, 19))
    assert y["from"] == "2026-10-19" and y["to"] == "2027-10-19" and set(y["areas"]) == {"work", "money", "love", "health"}
    for a in y["areas"].values():
        st = a["stretches"]
        assert st and st[0]["starts"] == "2026-10-19" and st[-1]["ends"] <= "2027-10-19"
        assert all(x["starts"] < x["ends"] for x in st) and all(b["starts"] == a_["ends"] for a_, b in zip(st, st[1:]))
        assert all(x["tone"] in ("best", "good", "steady", "slow", "care") and x["text"] for x in st)
    words = " ".join(x["text"] for a in y["areas"].values() for x in a["stretches"])
    for jargon in ("Dasha", "Bhukti", "house", "Jupiter", "Saturn", "nakshatra"):
        assert jargon not in words
    assert all(h["tone"] in ("best", "care") and h["areas"] for h in y["highlights"])


def test_goal_plan_has_steps_and_a_best_time():
    p = goals.plan(_chart(), "abroad", {"eca"}, date(2026, 10, 19))
    assert p["title"] == "Moving abroad" and p["source"]
    assert [s["done"] for s in p["steps"]].count(True) == 1
    b = p["best"]
    assert b is None or (b["starts"] >= "2026-10-19" and b["starts"] < b["ends"] and b["strength"] in ("strong", "favourable"))


def test_plans_api(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    assert client.get(f"/profiles/{pid}/plans").json()["plans"] == []
    assert client.put(f"/profiles/{pid}/plans/job", json={"step": "cv", "done": True}).status_code == 404  # not added
    assert client.post(f"/profiles/{pid}/plans", json={"goal": "job"}).status_code == 200
    assert client.put(f"/profiles/{pid}/plans/job", json={"step": "cv", "done": True}).status_code == 200
    assert client.put(f"/profiles/{pid}/plans/job", json={"step": "nope", "done": True}).status_code == 422
    assert client.post(f"/profiles/{pid}/plans", json={"goal": "lottery"}).status_code == 422
    d = client.get(f"/profiles/{pid}/plans").json()
    assert [p["goal"] for p in d["plans"]] == ["job"] and d["plans"][0]["steps"][0]["done"] is True
    assert "job" not in [c["goal"] for c in d["choices"]]
    client.delete(f"/profiles/{pid}/plans/job")
    assert client.get(f"/profiles/{pid}/plans").json()["plans"] == []
    assert client.get(f"/profiles/{pid}/year").status_code == 200
    assert client.get("/profiles/999/plans").status_code == 404


def test_guide_level_changes_the_chat_prompt_and_cache():
    p = {"id": 1, "chart": _chart(), "request": BODY}
    assert chat.GUIDE_NOTE in chat._system_text({**p, "level": "guide"})
    assert chat.GUIDE_NOTE not in chat._system_text(p)
