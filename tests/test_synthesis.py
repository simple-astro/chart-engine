"""Pre-synthesised chat context: weighed houses, planet context, daśā and transits."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import synthesis
from app.main import app

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _chart(**over):
    body = {"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata", **over}
    return {"chart": TestClient(app).post("/chart", json=body).json(), "request": body}


def test_planet_context():
    s = synthesis.build(_chart(), NOW)
    moon, sat = s["planets"]["Moon"], s["planets"]["Saturn"]
    assert moon["h"] == 12 and moon["with"] == ["Saturn"] and "Mars" in moon["aspected_by"]["malefic"]
    assert sat["aspects_h"] == [2, 6, 9] and sat["owns"] == [2, 3] and sat["nature"] == "malefic"
    assert s["planets"]["Venus"]["flags"] == ["combust"]


def test_houses_are_weighed():
    h = synthesis.build(_chart(), NOW)["houses"]
    assert h[12]["in"] == ["Moon", "Saturn"] and any("Saturn" in x for x in h[12]["-"])
    assert any("Viparita" in x for x in h[8]["+"])  # 8th lord Moon in the 12th
    assert all(v["net"] in ("strong", "good", "mixed", "weak") for v in h.values())


def test_dasha_and_transits_now():
    s = synthesis.build(_chart(), NOW)
    assert s["dasha"]["maha"]["lord"] == "Venus" and s["dasha"]["antar"]["lord"] == "Mercury"
    assert s["dasha"]["next_maha"]["lord"] == "Sun"
    t = s["transits_now"]
    assert t["Saturn"]["sign"] == "Pisces" and t["Saturn"]["h_from_moon"] == 5 and "sade_sati" not in t
    peak = synthesis.build(_chart(), datetime(2015, 6, 1, tzinfo=timezone.utc))["transits_now"]
    assert peak["Saturn"]["sign"] == "Scorpio" and peak["sade_sati"] == "peak phase"


def test_unknown_birth_time_is_flagged():
    s = synthesis.build(_chart(tob_unknown=True, tob="12:00:00"), NOW)
    assert "uncertain" in s["native"]["birth_time_unknown"]


def test_timeline_is_flat_and_labelled():
    s = synthesis.build(_chart(), NOW)
    tl = s["dasha"]["next_24_months"]
    assert tl[0] == {"maha": "Venus", "antar": "Mercury", "pratyantar": "Mercury", "starts": "2026-06-23", "ends": "2026-11-16"}
    assert all(p["antar"] == "Mercury" for p in tl)  # the whole window sits inside Mercury antardasha
    assert all(a["ends"] == b["starts"] for a, b in zip(tl, tl[1:]))
    assert s["dasha"]["antar"]["ends"] == "2029-04-23"


def test_transit_aspects_and_remedy_guide():
    s = synthesis.build(_chart(), NOW)
    assert s["transits_now"]["Jupiter"]["aspects_h"] == [2, 4, 12]  # Jupiter in Cancer = 8th from Sagittarius
    g = s["remedy_guide"]
    assert set(g["suitable_stones"]) == {"Jupiter", "Mars", "Sun"}  # lords of 1st, 5th, 9th for Sagittarius
    assert "Mercury" not in g["suitable_stones"] and g["planet_days"]["Mercury"] == "Wednesday"
    assert set(g["avoid_stones"]) == {"Venus", "Moon"}  # 6th and 8th lords (12th lord Mars is also 5th lord)
