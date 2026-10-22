"""Uranus, Neptune and Pluto: an optional extra, never one of the nine grahas."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
BODY = {"name": "t", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73, "lon": 76.78, "tz_name": "Asia/Kolkata"}


def test_chart_carries_outer_planets_apart_from_the_grahas():
    c = client.post("/chart", json=BODY).json()
    assert len(c["grahas"]) == 9 and "Uranus" not in c["grahas"]
    o = c["outer"]
    assert set(o) == {"Uranus", "Neptune", "Pluto"}
    # Lahiri, 1 Sep 1987: Uranus at the end of Scorpio, Neptune in Sagittarius, Pluto in Libra (both outer two retrograde)
    assert (o["Uranus"]["sign"], o["Neptune"]["sign"], o["Pluto"]["sign"]) == ("Scorpio", "Sagittarius", "Libra")
    assert o["Uranus"]["retrograde"] and o["Neptune"]["retrograde"]
    for g in o.values():
        assert 1 <= g["house"] <= 12 and set(g["kp"]) == {"sign_lord", "star_lord", "sub_lord", "sub_sub_lord"}


def test_outer_planets_follow_the_ayanamsa():
    lah = client.post("/chart", json=BODY).json()["outer"]["Pluto"]["longitude"]
    kp = client.post("/chart", json={**BODY, "ayanamsha": "krishnamurti"}).json()["outer"]["Pluto"]["longitude"]
    assert 0.05 < kp - lah < 0.2  # the KP ayanamsa is a few minutes smaller than Lahiri


def test_setting_shows_them_only_when_turned_on():
    index = (STATIC / "index.html").read_text()
    assert "localStorage.getItem('sj-outer')==='1'" in index and "seg('outer',[['off','Hide'],['on','Show']]" in index
    assert "outerOn(c).forEach" in index and "Uranus:'Ur',Neptune:'Ne',Pluto:'Pl'" in index
    pro = (STATIC / "pro.js").read_text()
    assert "localStorage.getItem('sj-outer') === '1'" in pro and "signOf === NATAL" in pro
    assert 'id="outerchk"' in (STATIC / "pro.html").read_text()
