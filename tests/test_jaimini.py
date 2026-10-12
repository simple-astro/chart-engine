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
    g = client.post("/chart", json=SS).json()["grahas"]
    assert [(k["short"], k["planet"]) for k in jaimini.chara_karakas(g, scheme=7)] == [
        ("AK", "Mercury"), ("AmK", "Mars"), ("BK", "Venus"), ("MK", "Jupiter"), ("PK", "Moon"), ("GK", "Saturn"),
        ("DK", "Sun")]
    # The app uses 8 karakas (the owner's practice): Rahu at 30 - 23 deg 54' = 6 deg 06' is lowest, so it is DK.
    j = client.post("/chart", json=SS).json()["jaimini"]
    assert j["scheme"] == 8 and [(k["short"], k["planet"]) for k in j["karakas"]] == [
        ("AK", "Mercury"), ("AmK", "Mars"), ("BK", "Venus"), ("MK", "Jupiter"), ("PiK", "Moon"), ("PK", "Saturn"),
        ("GK", "Sun"), ("DK", "Rahu")]
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


OWNER_LIKE = {"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


def test_all_twelve_arudhas_and_the_al_reading():
    c = client.post("/chart", json=OWNER_LIKE).json()
    j = c["jaimini"]
    assert [a["short"] for a in j["arudhas"]][:2] == ["AL", "A2"] and len(j["arudhas"]) == 12
    al = j["arudhas"][0]
    assert al["sign"] == j["arudha_lagna"]["sign"] == "Leo"  # Jupiter 5th from a Sagittarius lagna -> 5th again
    assert j["arudhas"][11]["sign"] == j["upapada"]["sign"]
    for a in j["arudhas"]:  # an arudha never sits in its own house or the 7th from it
        own = (c["lagna"]["sign_index"] + a["house"] - 1) % 12
        sign = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius",
                "Capricorn", "Aquarius", "Pisces"].index(a["sign"])
        assert sign not in (own, (own + 6) % 12)
    assert any("in your Arudha itself" in x for x in j["al_reading"])  # Sun, Mars, Mercury, Venus sit in Leo
    assert set(j["areas"]) == {"career", "love", "money"} and j["purpose"].startswith("Your Atmakaraka is")


def test_yogini_dasha_starts_from_the_birth_nakshatra():
    from datetime import datetime, timezone
    from core import yogini
    c = client.post("/chart", json=OWNER_LIKE).json()
    assert c["grahas"]["Moon"]["nakshatra"] == "Jyeshtha"  # 18 + 3 = 21 -> 5th yogini, Bhadrika
    ps = yogini.yogini_dasha(c["grahas"]["Moon"]["longitude"], datetime(1987, 9, 1, 8, 50, tzinfo=timezone.utc))
    assert ps[0]["yogini"] == "Bhadrika" and ps[0]["start"] < "1987-09-01"
    assert [p["yogini"] for p in ps[:8]] == ["Bhadrika", "Ulka", "Siddha", "Sankata", "Mangala", "Pingala",
                                             "Dhanya", "Bhramari"]
    assert ps[8]["yogini"] == "Bhadrika"  # the 36-year cycle repeats
    assert abs(sum(s["years"] for s in ps[1]["sub"]) - ps[1]["years"]) < 1e-9 and ps[1]["sub"][0]["yogini"] == "Ulka"
    y = yogini.summary(c, datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert y["current"]["yogini"] == "Bhadrika" and y["next"]["yogini"] == "Ulka"
    assert all(w not in p["text"].lower() for p in ps for w in ("death", "ruin", "disaster"))  # gentle wording


def test_arudha_lagna_only_falls_in_houses_3_4_5_9_10_11():
    """Satya Peetha: an arudha never sits in its own house or the 7th from it, so the AL is always 3/4/5/9/10/11."""
    import random
    from datetime import date, time, timedelta
    from app.routes import with_extras
    from core.chart import BirthData, compute_natal_chart
    rng, seen = random.Random(7), set()
    for _ in range(60):
        d = date(1940, 1, 1) + timedelta(days=rng.randint(0, 30000))
        c = with_extras(compute_natal_chart(BirthData(dob=d, tob=time(rng.randint(0, 23), rng.randint(0, 59)),
                                                      lat=rng.uniform(8, 35), lon=rng.uniform(68, 95),
                                                      tz_name="Asia/Kolkata", name="")))
        seen.add(c["lagna"]["sign"])
        for a in c["jaimini"]["arudhas"]:
            assert (a["in_house"] - a["house"]) % 12 not in (0, 6)
        assert c["jaimini"]["arudhas"][0]["in_house"] in (3, 4, 5, 9, 10, 11)
    assert len(seen) >= 8
