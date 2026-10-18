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


def test_accuracy_levels_and_next_step(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    a = c.get(f"/profiles/{pid}/accuracy").json()
    assert a["label"] == "Rough" and a["next"]["title"] == "Add 3 past events with the month"
    for e in EV:
        y, m, d = map(int, e["date"].split("-"))
        c.post(f"/profiles/{pid}/events", json={"kind": e["kind"], "year": y, "month": m, "day": d})
    a = c.get(f"/profiles/{pid}/accuracy").json()
    assert a["label"] == "Fair" and "before your Venus period" in a["next"]["title"]  # all six in one Mahadasha
    assert "can't test your chart much" in a["why"]
    c.get(f"/profiles/{pid}/events/birth-time")                                   # 14:20 is not the best fit
    assert not c.get(f"/profiles/{pid}/accuracy").json()["checks"][3]["ok"]


def test_a_loss_is_recorded_but_never_read_against_the_chart(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    for e in EV[:3]:
        y, m, d = map(int, e["date"].split("-"))
        c.post(f"/profiles/{pid}/events", json={"kind": e["kind"], "year": y, "month": m, "day": d})
    v = c.post(f"/profiles/{pid}/events", json={"kind": "loss", "year": 2019, "month": 3}).json()
    loss = next(e for e in v["events"] if e["kind"] == "loss")
    assert loss["label"] == "Loss of a family member" and loss["check"]["fit"] == "noted"
    assert v["summary"]["events"] == 3                                   # not counted in the fit score
    assert len(c.get(f"/profiles/{pid}/events/birth-time").json()["labels"]) == 3   # nor in rectification


def test_new_past_events_use_look_back_matters_only():
    from datetime import date
    from app import life_events as L
    from core import kp_predict as K
    c = with_extras(compute_chart(ChartRequest(**REQ)))
    for kind in ("love", "money_earned", "windfall", "long_journey", "family_trip", "pilgrimage", "initiation",
                 "school", "away", "debt_cleared", "money_loss"):
        r = L.check(c, kind, date(2015, 6, 1), "month")
        assert r["fit"] in ("fits", "partly", "no") and r["why"], kind
    assert "waiting for our astrologers' review" in L.check(c, "pilgrimage", date(2015, 6, 1), "month")["why"]
    assert not set(K.LOOKBACK) & set(K.TOPICS)          # never timed or predicted
    assert L.check(c, "parent_illness", date(2015, 6, 1), "month")["fit"] == "noted"
