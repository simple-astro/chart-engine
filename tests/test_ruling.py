"""KP ruling planets (core/ruling.py) and the day lord from the local sunrise."""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import app
from core import ruling as R

WPG, DELHI = (49.8951, -97.1384), (28.6139, 77.2090)
at = lambda tz, *a: datetime(*a, tzinfo=ZoneInfo(tz))


def test_day_lord_runs_from_sunrise_to_sunrise():
    assert R.day_lord(at("America/Winnipeg", 2026, 10, 19, 20, 0), *WPG) == "Moon"   # Monday evening (UTC: Tuesday)
    assert R.day_lord(at("America/Winnipeg", 2026, 10, 20, 7, 0), *WPG) == "Moon"    # Tuesday before sunrise (08:03)
    assert R.day_lord(at("America/Winnipeg", 2026, 10, 20, 9, 0), *WPG) == "Mars"    # Tuesday after sunrise
    assert R.day_lord(at("Asia/Kolkata", 2026, 10, 20, 3, 0), *DELHI) == "Moon"
    assert R.day_lord(at("Asia/Kolkata", 2026, 10, 20, 7, 0), *DELHI) == "Mars"


def test_ruling_planets_in_strength_order_with_node_agents():
    r = R.ruling_planets(at("America/Winnipeg", 2026, 10, 19, 10, 9, 23), *WPG)
    assert [x["role"] for x in r["rows"]] == R.ROLES
    # Lagna Libra in Vishakha (Jupiter), Moon in Capricorn in Shravana (Moon), a Monday
    assert [x["planet"] for x in r["rows"]] == ["Jupiter", "Venus", "Moon", "Saturn", "Moon"]
    assert r["ruling_planets"] == ["Jupiter", "Venus", "Moon", "Saturn", "Rahu"]     # Rahu in Aquarius acts for Saturn
    assert r["nodes"] == [{"planet": "Rahu", "sign": "Aquarius", "for": "Saturn"}]


def test_endpoint():
    c = TestClient(app)
    r = c.post("/ruling-planets", json={"lat": WPG[0], "lon": WPG[1], "tz_name": "America/Winnipeg",
                                        "at": "2026-10-19T10:09:23-05:00"})
    assert r.status_code == 200 and r.json()["ruling_planets"][0] == "Jupiter"
    assert c.post("/ruling-planets", json={"lat": 0, "lon": 0, "tz_name": "Foo/Bar"}).status_code == 422
