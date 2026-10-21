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


def _events_fitting(true_tob: str, kinds=("school", "degree", "job", "married", "child", "abroad", "home", "promotion")):
    """Events made to fit the chart cast for ``true_tob``: the first month of adult life each kind fits."""
    ch = with_extras(compute_chart(ChartRequest(**{**REQ, "tob": true_tob})))
    out, used = [], set()
    for kind in kinds:
        for y in range(2000, 2025):
            for m in range(1, 13):
                d = date(y, m, 1)
                if L.check(ch, kind, d, "month")["fit"] == "fits" and (y, m) not in used:
                    used.add((y, m))
                    out.append({"kind": kind, "date": d.isoformat(), "precision": "month"})
                    break
            else:
                continue
            break
    return out


def test_whole_day_search_finds_a_window_with_the_true_time_in_it():
    at = lambda tob: with_extras(compute_chart(ChartRequest(**{**REQ, "tob": tob, "tob_unknown": False})))
    ev = _events_fitting("14:20:00")
    assert len(ev) >= 6
    r = L.birth_time_check({**REQ, "tob_unknown": True}, ev, at, date(2026, 10, 18), unknown=True)
    assert r["scope"] == "day" and len(r["rows"]) == 360 and not any(x["yours"] for x in r["rows"])
    assert r["best"] == len(ev)                                    # something fits every event
    true_t = "14:20"
    assert any(w["from"] <= true_t <= w["to"] for w in r["windows"])
    assert r["windows"] and all(w["lagna"] for w in r["windows"])
    assert r["narrowing"] is (r["suggest"] is not None)


def test_a_part_of_the_day_limits_the_search():
    at = lambda tob: with_extras(compute_chart(ChartRequest(**{**REQ, "tob": tob})))
    ev = _events_fitting("14:20:00")
    r = L.birth_time_check({**REQ, "tob_unknown": True}, ev, at, date(2026, 10, 18), unknown=True, between=(720, 1079))
    assert r["rows"][0]["tob"] == "12:00" and r["rows"][-1]["tob"] <= "17:59" and len(r["rows"]) == 90


def test_events_that_fit_most_of_the_day_do_not_narrow_anything():
    fixed = with_extras(compute_chart(ChartRequest(**REQ)))
    ev = [{"kind": k, "date": d, "precision": "month"} for k, d in (("job", "2012-07-01"), ("married", "2016-04-10"),
                                                                    ("child", "2017-05-27"), ("abroad", "2020-07-11"))]
    r = L.birth_time_check({**REQ, "tob_unknown": True}, ev, lambda tob: fixed, date(2026, 10, 18), unknown=True)
    # every time of day gives the same chart here, so every time ties: the events say nothing about the hour
    assert r["narrowing"] is False and r["suggest"] is None and r["strength"] == "weak"
    assert "can't narrow" in r["text"] and "does not narrow" in r["note"]


def test_year_only_events_cannot_find_an_unknown_time():
    at = lambda tob: with_extras(compute_chart(ChartRequest(**{**REQ, "tob": tob})))
    ev = [{"kind": k, "date": d, "precision": "year"} for k, d in (("job", "2012-01-01"), ("married", "2016-01-01"),
                                                                   ("child", "2017-01-01"), ("abroad", "2020-01-01"))]
    r = L.birth_time_check({**REQ, "tob_unknown": True}, ev, at, date(2026, 10, 18), unknown=True)
    assert r["strength"] == "weak"


def test_unknown_time_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json={**REQ, "tob": "12:00:00", "tob_unknown": True}).json()["id"]
    assert c.get(f"/profiles/{pid}/events/birth-time").status_code == 422        # needs 4 events when the time is unknown
    for e in _events_fitting("14:20:00")[:5]:
        y, m, d = map(int, e["date"].split("-"))
        c.post(f"/profiles/{pid}/events", json={"kind": e["kind"], "year": y, "month": m})
    r = c.get(f"/profiles/{pid}/events/birth-time")
    assert r.status_code == 200 and r.json()["scope"] == "day" and r.json()["unknown"] is True
    assert c.get(f"/profiles/{pid}/events/birth-time?part=afternoon").json()["part"] == "afternoon"
    assert c.get(f"/profiles/{pid}/events/birth-time?part=dusk").status_code == 422
