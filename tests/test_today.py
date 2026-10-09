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
    assert len(d["do"]) == 3 and 1 <= len(d["avoid"]) <= 3 and all(x["text"] and x["why"] for x in d["do"] + d["avoid"])
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


def test_same_day_reads_differently_for_different_charts():
    """Friday 2026-10-09, Moon in Virgo. Venus rules the 11th for Sagittarius but the 9th for Aquarius,
    and Virgo is the 8th house for an Aquarius lagna."""
    day = date(2026, 10, 9)
    sag = T.today(day, **DELHI, lagna_sign=8, birth_nakshatra=17, birth_moon_sign=7, antar="Mercury", antar_sign=2)
    aqu = T.today(day, **DELHI, lagna_sign=10, birth_nakshatra=4, birth_moon_sign=1, antar="Rahu", antar_sign=0)
    why = lambda d, k: [x["why"] for x in d[k]]
    assert "Venus rules Friday and your 11th house" in why(sag, "do")
    assert "your Mercury period works through your 10th house" in why(sag, "do")
    assert "Venus rules Friday and your 9th house" in why(aqu, "do")
    assert "your Rahu period works through your 3rd house" in why(aqu, "do")
    assert "the Moon passes your 8th house today" in why(aqu, "avoid")
    assert not {x["text"] for x in sag["do"]} & {x["text"] for x in aqu["do"]}


def test_moon_in_the_8th_from_lagna_goes_to_avoid():
    day = date(2026, 10, 9)
    moon = T.compute_panchang(day, **DELHI).moon_sign_index
    d = T.today(day, **DELHI, lagna_sign=(moon - 7) % 12, birth_nakshatra=0, birth_moon_sign=(moon + 1) % 12)
    assert any("8th house" in x["why"] for x in d["avoid"]) and not any("8th house" in x["why"] for x in d["do"])
