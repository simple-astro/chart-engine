"""Coming up for you: period changes (strong) and the sky changes that matter to this chart (hints)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import upcoming
from app.main import app
from app.routes import with_extras
from tests.test_admin import _tester, gated  # noqa: F401  (fixture)

H1 = {"name": "H1", "dob": "1950-06-07", "tob": "22:30:00", "lat": 28.6667, "lon": 77.2167, "tz_name": "Asia/Kolkata"}
CHILD = {**H1, "name": "Kid", "dob": "2016-03-01"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("TESTER_ACCESS_CODES", raising=False)
    return TestClient(app)


def _items(client, body, tz="Asia/Kolkata"):
    pid = client.post("/profiles", json=body).json()["id"]
    r = client.get(f"/profiles/{pid}/upcoming?tz={tz}")
    assert r.status_code == 200, r.text
    return r.json()


def test_items_are_dated_labelled_and_in_order(client):
    d = _items(client, H1)
    items = d["items"]
    assert items and [i["date"] for i in items] == sorted(i["date"] for i in items)
    assert all(i["date"] > d["today"] for i in items)
    for i in items:
        assert i["title"] and i["meaning"] and i["prepare"].endswith(".") and i["ask"]
        assert (i["kind"], i["confidence"]) in (("period", "strong"), ("sky", "hint"))
    periods = [i for i in items if i["kind"] == "period"]
    assert periods and all(i["until"] >= i["date"] for i in periods)
    assert sum(i["level"] == "praty" for i in periods) <= 2


def test_the_tip_comes_from_what_the_card_shows():
    c = with_extras(TestClient(app).post("/chart", json=H1).json())
    for it in upcoming.period_items(c, date(2026, 10, 11)):
        if it["good_for"]:
            shown = it["good_for"][:3]
            assert any(upcoming.GOOD_FOR[t][1][:20].lower() in it["prepare"].lower()
                       for t in upcoming.GOOD_FOR if upcoming.GOOD_FOR[t][0] in shown)


def test_a_child_gets_no_marriage_or_job_advice():
    c = with_extras(TestClient(app).post("/chart", json=CHILD).json())
    for it in upcoming.period_items(c, date(2026, 10, 11), age=10.6):
        assert not set(it["good_for"]) & {"marriage", "love", "career", "a job change", "business", "property"}


def test_saturn_from_the_moon_reads_as_sade_sati_and_nodes_never_turn_direct():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from core.transit_scan import TransitEvent
    c = with_extras(TestClient(app).post("/chart", json=H1).json())
    moon = c["grahas"]["Moon"]["sign_index"]
    t = datetime(2027, 1, 1, tzinfo=timezone.utc)
    fake = (TransitEvent("ingress", "Saturn", t, {"to_sign_index": (moon - 1) % 12, "direction": "direct"}),
            TransitEvent("ingress", "Rahu", t, {"to_sign_index": 3, "direction": "retrograde"}),
            TransitEvent("station", "Mars", t, {"direction": "direct"}))
    old = upcoming._sky
    upcoming._sky = lambda *a: fake
    try:
        its = upcoming.sky_items(c, date(2026, 10, 11), {"maha": "Rahu", "antar": "Jupiter"}, ZoneInfo("UTC"))
    finally:
        upcoming._sky = old
    titles = [i["title"] for i in its]
    assert "Sade Sati begins" in titles
    rahu = next(i for i in its if i["planet"] == "Rahu")
    assert "Mahadasha lord" in rahu["title"] and "backwards" not in rahu["meaning"]
    assert not any(i["planet"] == "Mars" for i in its)  # not a dasha lord, not a slow planet


def test_upcoming_is_private(gated):
    a, b = _tester(), _tester()
    pid = a.post("/profiles", json=H1).json()["id"]
    assert a.get(f"/profiles/{pid}/upcoming").status_code == 200
    assert b.get(f"/profiles/{pid}/upcoming").status_code == 404
    assert a.get(f"/profiles/{pid}/upcoming?tz=Mars/Base").status_code == 422
