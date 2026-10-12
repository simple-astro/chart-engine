"""Jaimini Phase A: chara karakas, karakamsa, arudha lagna and upapada.

Reference: a third-party software printout (Lahiri, true node) for 23 Dec 1986 07:50:21 at Chandigarh lists the
karakas Mercury AK, Mars AmK, Venus BK, Jupiter MK, Moon PK, Saturn GK, Sun DK and Mercury in Aquarius in the D9.
"""
from fastapi.testclient import TestClient

from app import synthesis
from app.main import app
from core import jaimini

client = TestClient(app)
SS = {"dob": "1986-12-23", "tob": "07:50:21", "lat": 30.7, "lon": 76.8, "tz_name": "Asia/Kolkata",
      "ayanamsha": "lahiri", "node_type": "true"}


def test_karakas_match_the_printout():
    j = client.post("/chart", json=SS).json()["jaimini"]
    assert [(k["short"], k["planet"]) for k in j["karakas"]] == [
        ("AK", "Mercury"), ("AmK", "Mars"), ("BK", "Venus"), ("MK", "Jupiter"), ("PK", "Moon"), ("GK", "Saturn"),
        ("DK", "Sun")]
    assert j["karakamsa"]["sign"] == "Aquarius" and "Rahu" in j["karakamsa"]["planets"]


def test_arudha_rules():
    c = client.post("/chart", json=SS).json()
    j = c["jaimini"]
    # Sagittarius lagna, Jupiter in Aquarius (3rd) -> 3rd again from Aquarius = Aries.
    assert j["arudha_lagna"]["sign"] == "Aries" and j["arudha_lagna"]["house"] == 5
    # 12th = Scorpio; Mars (with Jupiter) beats Ketu (alone); Scorpio->Aquarius = 4th, 4th again = Taurus,
    # which is 7th from Scorpio, so the 10th from Taurus: Aquarius.
    assert j["upapada"]["sign"] == "Aquarius" and "3rd house" in j["upapada"]["note"]
    signs = {"Jupiter": 10, "Mars": 10, "Ketu": 5, "_deg": {}}
    assert jaimini.arudha(8, signs) == 0


def test_eight_karaka_scheme_adds_rahu_counted_backwards():
    g = client.post("/chart", json=SS).json()["grahas"]
    ks = jaimini.chara_karakas(g, scheme=8)
    assert len(ks) == 8 and ks[4]["karaka"] == "Pitrikaraka"
    rahu = next(k for k in ks if k["planet"] == "Rahu")
    assert abs(rahu["degree"] - (30 - g["Rahu"]["degrees_in_sign"])) < 1e-3


def test_sukh_gets_jaimini_for_description_not_timing():
    c = client.post("/chart", json=SS).json()
    out = synthesis.build({"chart": c, "request": {**SS, "place": "Chandigarh"}})
    assert "AK=Mercury" in out["jaimini"]["karakas"] and "never for timing" in out["jaimini"]["rule"]
    assert out["jaimini"]["UL"].startswith("Aquarius H3")
