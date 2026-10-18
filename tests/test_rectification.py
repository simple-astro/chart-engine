"""Birth time rectification: events judged against nearby birth times, with an honest strength note."""
from datetime import date

from fastapi.testclient import TestClient

from app import life_events as L
from app.main import app
from app.routes import chart as compute_chart, with_extras
from app.schemas import ChartRequest

REQ = {"name": "t", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata",
       "ayanamsha": "krishnamurti", "node_type": "mean", "tob_unknown": False}
EV = [{"kind": k, "date": d, "precision": "day"} for k, d in
      (("job", "2012-07-01"), ("married", "2016-04-10"), ("child", "2017-05-27"), ("abroad", "2020-07-11"),
       ("job", "2021-08-01"), ("child", "2022-06-04"))]


def test_finds_the_best_window_and_says_it_is_only_a_hint():
    at = lambda tob: with_extras(compute_chart(ChartRequest(**{**REQ, "tob": tob})))
    r = L.birth_time_check(REQ, EV, at, date(2026, 10, 18))
    assert len(r["rows"]) == 31 and next(x for x in r["rows"] if x["yours"])["tob"] == "14:20"
    assert r["best"] == 6 and r["window"] == ["14:24", "14:36"] and r["suggest"] == "14:28"
    assert r["strength"] == "weak" and r["mahadashas"] == ["Venus"]  # one Mahadasha, high chance: only a hint
    assert "only a hint" in r["note"].lower()


def test_needs_three_events(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    assert c.get(f"/profiles/{pid}/events/birth-time").status_code == 422
