"""Cheshta Bala (BPHS 27.24) and Graha Yuddha, shown for study."""
from fastapi.testclient import TestClient

from app.main import app
from core.cheshta import cheshta, motion

Q = {"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


def test_values_follow_the_classical_pattern():
    c = TestClient(app).post("/chart", json=Q).json()
    p = c["cheshta"]["planets"]
    assert all(0 <= x["value"] <= 60 for x in p.values()) and set(p) == {"Sun", "Moon", "Mars", "Mercury", "Jupiter",
                                                                          "Venus", "Saturn"}
    assert p["Jupiter"]["name"] == "Vakra" and p["Jupiter"]["value"] > 40      # retrograde, away from the Sun: strong
    assert p["Mars"]["value"] < 5 and p["Venus"]["value"] < 5                   # beside the Sun in Leo: weak
    assert p["Sun"]["name"] == "Ayana Bala" and abs(p["Sun"]["value"] - 40.5) < 0.5
    assert p["Moon"]["name"] == "Paksha Bala" and abs(p["Moon"]["value"] - 30.9) < 0.5
    assert c["cheshta"]["wars"] == [] and c["cheshta"]["closest"]["planets"] == ["Mars", "Venus"]


def test_motion_names():
    assert motion("Saturn", -0.01)["name"] == "Vakra"
    assert motion("Saturn", 0.002)["name"] == "Vikala"
    assert motion("Mars", 0.52)["name"] == "Sama" and motion("Mars", 0.9)["name"] == "Ati-chara"


def test_a_planetary_war_names_the_winner():
    # any day in 2026 with two of Mars, Mercury, Jupiter, Venus and Saturn within 1 degree
    import swisseph as swe
    jd0 = swe.julday(2026, 1, 1, 12)
    found = next((cheshta(jd0 + d) for d in range(0, 400) if cheshta(jd0 + d)["wars"]), None)
    assert found, "expected at least one planetary war in 2026"
    w = found["wars"][0]
    assert w["gap"] < 1 and w["winner"] in w["planets"] and w["loser"] in w["planets"] and w["winner"] != w["loser"]
