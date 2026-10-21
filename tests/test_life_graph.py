"""The Life graph data: promise, Dasha windows, monthly transit lane, best windows and the person's own events."""
from fastapi.testclient import TestClient

from app.main import app

REQ = {"name": "t", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    return c, c.post("/profiles", json=REQ).json()["id"]


def test_life_graph_shape(tmp_path, monkeypatch):
    c, pid = _client(tmp_path, monkeypatch)
    d = c.get(f"/profiles/{pid}/graph/life?topic=career&ahead=24").json()
    assert d["topic"] == "career" and d["promise"]["cusp"] == 10 and d["promise"]["verdict"]
    assert len(d["transit"]) == 24 and d["windows"] and d["windows"][0]["verdict"] in ("strong", "favourable", "mixed", "challenging")
    assert d["windows"][0]["starts"] < d["windows"][-1]["ends"] and d["from"] <= d["today"] <= d["to"]
    assert all({"date", "score", "notes"} <= set(t) for t in d["transit"])
    assert {t["key"] for t in d["topics"]} >= {"career", "marriage", "money", "property", "foreign"}
    assert all(t["key"] not in ("illness", "accident", "divorce") for t in d["topics"])  # no risk topics in the picker


def test_looking_back_adds_months_and_the_persons_own_events(tmp_path, monkeypatch):
    c, pid = _client(tmp_path, monkeypatch)
    c.post(f"/profiles/{pid}/events", json={"kind": "job", "year": 2022, "month": 6})
    c.post(f"/profiles/{pid}/events", json={"kind": "married", "year": 2016, "month": 4})   # another matter
    d = c.get(f"/profiles/{pid}/graph/life?topic=career&ahead=12&back=60").json()
    assert len(d["transit"]) == 72 and d["from"] < "2022-01-01"
    assert [(e["label"], e["date"][:7]) for e in d["events"]] == [("Started a job", "2022-06")]
    assert d["events"][0]["fit"] in ("fits", "partly", "no")
    assert all(b > d["today"] for _, b in d["best_ahead"]) and len(d["best_ahead"]) <= 3
    assert c.get(f"/profiles/{pid}/graph/life?topic=career&ahead=12").json()["events"] == []   # not looking back


def test_bad_topic_and_other_peoples_charts(tmp_path, monkeypatch):
    c, pid = _client(tmp_path, monkeypatch)
    assert c.get(f"/profiles/{pid}/graph/life?topic=illness").status_code == 422
    assert c.get(f"/profiles/{pid}/graph/life?topic=nonsense").status_code == 422
    assert c.get("/profiles/999/graph/life?topic=career").status_code == 404
