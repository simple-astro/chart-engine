"""Married life: ratings compared with the kootas, habits for the weak areas, talk days and patience days."""
from datetime import date

import yaml
from fastapi.testclient import TestClient

from app import marriage, storage
from app.main import app
from app.remedies import library

GROOM = {"name": "Ravi K", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73, "lon": 76.78, "tz_name": "Asia/Kolkata"}
BRIDE = {"name": "Asha", "dob": "1990-01-12", "tob": "06:00:00", "lat": 30.73, "lon": 76.78, "tz_name": "Asia/Kolkata"}
HABITS = [{"kind": "couple", "slug": f"c-{a}", "area": a, "who": "both", "title": f"Habit {a}", "text": "Do a kind thing."}
          for a in ("gana", "bhakoot", "maitri", "yoni", "vashya", "nadi", "general")]


def test_couple_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    library.import_items(HABITS)
    g, b = c.post("/profiles", json=GROOM).json()["id"], c.post("/profiles", json=BRIDE).json()["id"]
    v = c.get(f"/couples/{g}/{b}").json()
    assert v["married"] is False and len(v["compare"]["rows"]) == 6 and len(v["days"]) == 28
    assert c.put(f"/couples/{g}/{b}", json={"ratings": {"gana": 9}}).status_code == 422
    c.put(f"/couples/{g}/{b}", json={"married": True})
    ratings = {k: 2 for k, _, _ in marriage.AREAS}
    v = c.put(f"/couples/{g}/{b}", json={"ratings": ratings, "trend": "hard_then_better"}).json()
    assert v["married"] and v["compare"]["rated"] == 6 and v["compare"]["text"].startswith("Your experience matches")
    assert v["habits"] and v["habits"][-1]["area_label"] == "Every couple"
    assert all(d["kind"] in (None, "talk", "patience") for d in v["days"])
    c.post(f"/profiles/{g}/events", json={"kind": "married", "year": 2016, "month": 4, "day": 10})
    v = c.put(f"/couples/{g}/{b}", json={"plan": "start"}).json()
    assert v["wedding"] == "2016-04-10" and v["early_years"] and v["plan"]["day"] == 1
    v = c.put(f"/couples/{g}/{b}", json={"tick": True}).json()
    assert v["plan"]["done_today"] and v["plan"]["done"] == 1
    assert "couples" in c.get(f"/profiles/{g}/couple-day").json()


def test_patience_day_is_the_moon_8th_from_a_moon():
    groom = {"meta": {"ayanamsha": "krishnamurti"}, "grahas": {"Moon": {"sign_index": 7, "nakshatra_index": 17}}}
    bride = {"meta": {"ayanamsha": "krishnamurti"}, "grahas": {"Moon": {"sign_index": 3, "nakshatra_index": 7}}}
    ds = {d["date"]: d for d in marriage.days(groom, bride, date(2026, 10, 19), 31, "America/Winnipeg", ("Ravi", "Asha"))}
    assert ds["2026-10-21"]["kind"] == "patience" and ds["2026-10-21"]["who"] == ["Asha"]   # Moon in Aquarius
    assert ds["2026-10-30"]["who"] == ["Ravi"]                                                 # Moon in Gemini
    assert ds["2026-10-23"]["kind"] == "talk"


def test_couple_habits_never_mention_separation():
    import pytest
    from app.remedies.schema import Invalid, validate
    with pytest.raises(Invalid):
        validate("couple", {**HABITS[0], "text": "If nothing works, consider separation."})
