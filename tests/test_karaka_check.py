"""Past events by natural karakas (draft rules), beside the KP check."""
from datetime import date

from fastapi.testclient import TestClient

from app import karaka_check as K
from app import life_events as L
from app.main import app

REQ = {"name": "t", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata",
       "ayanamsha": "pushya"}


def test_marriage_fits_by_karaka_and_reasons_name_it():
    c = TestClient(app).post("/chart", json=REQ).json()
    r = K.check(c, "marriage", *L.span(date(2016, 4, 10), "day"))
    assert r["fit"] == "fits" and "Venus is the karaka" in r["why"] and "7th" in r["why"]
    assert K.check(c, None, date(2019, 3, 1), date(2019, 4, 1))["fit"] == "noted"   # a loss is never read
    assert 0 <= K.base_rate(c, "marriage", date(1987, 9, 1), date(2026, 10, 18)) <= 1


def test_events_view_carries_both_methods(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    for k, y, m, d in (("married", 2016, 4, 10), ("child", 2017, 5, 27), ("job", 2012, 7, 1)):
        v = c.post(f"/profiles/{pid}/events", json={"kind": k, "year": y, "month": m, "day": d}).json()
    assert v["karaka"]["events"] == 3 and "draft" in v["karaka"]["note"]
    assert all(e["karaka"]["fit"] in ("fits", "partly", "no") for e in v["events"])
