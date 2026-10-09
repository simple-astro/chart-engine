"""Today for one person."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app import today as T
from app.main import app

DELHI = dict(lat=28.6139, lon=77.209, tz_name="Asia/Kolkata")


def test_helpful_and_difficult_planets_by_lagna():
    good, bad = T.chart_planets(0)        # Aries: Mars (1, 8) helps, Mercury (3, 6) does not
    assert good[0] == "Mars" and {"Sun", "Jupiter"} <= set(good) and "Mercury" in bad and "Mars" not in bad
    good, _ = T.chart_planets(6)          # Libra: Saturn owns 4 and 5 — yogakaraka first
    assert good[0] == "Saturn"


def test_horas_follow_the_chaldean_order_from_the_day_lord():
    d = T.today(date(2026, 10, 8), **DELHI, lagna_sign=7, birth_nakshatra=17, birth_moon_sign=7)  # a Thursday
    hs = d["horas"]
    assert len(hs) == 24 and hs[0]["lord"] == "Jupiter" and hs[1]["lord"] == "Mars" and hs[12]["start"] < hs[23]["end"]
    assert all(datetime.fromisoformat(a["end"]) == datetime.fromisoformat(b["start"]) for a, b in zip(hs, hs[1:]))


def test_today_card_content():
    d = T.today(date(2026, 10, 8), **DELHI, lagna_sign=7, birth_nakshatra=17, birth_moon_sign=7,
                maha="Venus", antar="Mercury")
    assert d["weekday"] == "Thursday" and d["rating"]["label"] and d["rating"]["why"]
    assert 1 <= len(d["do"]) <= 3 and 1 <= len(d["avoid"]) <= 3 and d["avoid"][-1].startswith(("Starting new", "Starting"))
    assert d["direction"]["avoid"] == "south" and "curd" in d["direction"]["fix"]
    assert d["number"]["value"] == T.NUMBER[d["colour"]["planet"]]
    assert d["upay"]["mantra"] == "Om Gurave Namah" and d["sukh"].startswith("Your Mercury period")
    for w in d["best_times"]:
        assert w["start"] < w["end"] and not (w["start"] < d["rahu_kalam"][1] and w["end"] > d["rahu_kalam"][0])


def test_difficult_day_lord_switches_the_colour():
    # Aries lagna: Mercury owns 3 and 6, so on a Wednesday wear Mars's colour instead of green.
    d = T.today(date(2026, 10, 7), **DELHI, lagna_sign=0, birth_nakshatra=0, birth_moon_sign=0)
    assert d["weekday"] == "Wednesday" and d["colour"]["planet"] == "Mars" and d["colour"]["avoid"] == "green"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    return TestClient(app)


def test_endpoint(client):
    body = dict(date="2026-10-08", **DELHI, lagna_sign=7, birth_nakshatra=17, birth_moon_sign=7, antar="Mercury")
    r = client.post("/today", json=body)
    assert r.status_code == 200 and r.json()["upay"]["mantra"]
    assert client.post("/today", json={**body, "antar": "Pluto"}).status_code == 422
    assert client.post("/today", json={**body, "tz_name": "Nowhere/City"}).status_code == 422


def test_best_times_never_overlap_rahu_kaal_or_yamaganda():
    for i in range(14):
        d = T.today(date(2026, 10, 1 + i), **DELHI, lagna_sign=8, birth_nakshatra=10, birth_moon_sign=3)
        for w in d["best_times"]:
            for a, b in (d["rahu_kalam"], d["yamaganda"]):
                assert not (w["start"] < b and w["end"] > a), (d["date"], w)
