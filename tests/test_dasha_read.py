"""Vimshottari period readings (app/dasha_read.py)."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import dasha_read as D
from app.main import app

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
FEAR = ("death", "die ", "accident", "disease", "illness", "ruin", "curse", "disaster", "danger", "doom")


def chart(dob="1987-09-01", tob="14:20:00", lat=30.7333, lon=76.7794, tz="Asia/Kolkata"):
    return TestClient(app).post("/chart", json={"dob": dob, "tob": tob, "lat": lat, "lon": lon, "tz_name": tz, "ayanamsha": "krishnamurti"}).json()


@pytest.fixture(scope="module")
def own():
    return chart()


def test_running_periods_read_from_the_chart(own):
    r = D.summary(own, NOW)
    md, ad = r["now"][0], r["now"][1]
    assert (md["level"], md["lord"]) == ("Mahadasha", "Venus")
    # Sagittarius Lagna: Venus rules the 6th and 11th and sits in Leo, the 9th
    assert md["reading"]["headline"].startswith("Venus rules your 6th and 11th and sits in your 9th")
    # Mercury runs both the Antardasha and the Pratyantar: one card, not two identical ones
    assert ad["lord"] == "Mercury" and ad["level"] == "Antardasha and Pratyantar" and len(r["now"]) == 2
    assert any("good position from Venus" in p for p in ad["reading"]["points"])
    assert [x["level"] for x in r["next"]] == ["Next Antardasha", "Next Mahadasha"]
    assert r["next"][1]["lord"] == "Sun" and "own sign" in " ".join(r["next"][1]["reading"]["points"])


def test_nodes_act_for_their_sign_lord(own):
    ke = D.interpret(own, "Ketu")          # Ketu in Virgo
    assert "acts for Mercury" in ke["points"][0]
    ra = D.interpret(own, "Rahu")          # Rahu in Pisces
    assert "acts for Jupiter" in ra["points"][0]


def test_yoga_names_are_not_doubled(own):
    text = " ".join(p for x in D.summary(own, NOW)["now"] for p in x["reading"]["points"])
    assert "yoga yoga" not in text and "Raja yogas" in text


@pytest.mark.parametrize("args", [("1987-09-01", "14:20:00"), ("1990-01-15", "06:05:00"), ("1975-06-30", "22:40:00")])
def test_every_lord_reads_gently(args):
    c = chart(*args)
    for lord in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        r = D.interpret(c, lord, over="Saturn")
        text = (r["headline"] + " " + " ".join(r["points"])).lower()
        assert r["headline"] and r["points"]
        assert not any(w in text for w in FEAR), (lord, text)
        assert " and and " not in text


def test_chart_carries_the_readings(own):
    assert set(own["dasha_read"]) == {"now", "next", "headlines", "birth", "ayanamsha"}
    assert len(own["dasha_read"]["headlines"]) == len({d["lord"] for d in own["dasha"]})


def test_tara_bala_counts_from_the_birth_star(own):
    # Moon in Jyeshtha; Venus in Purva Phalguni: 3rd in the nine-star cycle (Vipat)
    assert D.tara(own, "Venus")[:2] == (3, "Vipat Tara")
    assert D.tara(own, "Moon")[:2] == (1, "Janma Tara")
    text = " ".join(D.interpret(own, "Venus")["points"])
    assert "Tara Bala" in text and "Vipat Tara" in text


def test_vargottama_is_named_in_the_reading(own):
    assert any(p.startswith("It is Vargottama") for p in D.interpret(own, "Sun")["points"])      # Leo in D1 and D9
    assert not any(p.startswith("It is Vargottama") for p in D.interpret(own, "Venus")["points"])


def test_seventh_tara_is_not_named_with_a_fear_word():
    assert "the 7th star" == D.TARA[7][0] and "Naidhana" not in D.TARA[7][0] + D.TARA[7][1]


def test_ayanamsha_note_gives_the_lahiri_dates(own):
    r = D.summary(own, NOW)
    assert r["birth"].startswith("1987-09-01T08:50")
    ay = r["ayanamsha"]
    assert ay["name"] == "krishnamurti" and ay["label"] == "KP (Krishnamurti)"
    # Lahiri puts the Venus Mahadasha 45 days later: 21 Sep 2010 in India (what most apps show)
    assert ay["lahiri"]["shift_days"] == 45 and ay["lahiri"]["md_start"].startswith("2010-09-20T23:45")
    lah = TestClient(app).post("/chart", json={"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794,
                                                "tz_name": "Asia/Kolkata", "ayanamsha": "lahiri"}).json()
    assert D.summary(lah, NOW)["ayanamsha"] == {"name": "lahiri", "label": "Lahiri"}
    # computing the note must not leave Swiss Ephemeris in the Lahiri frame for the next chart
    assert chart()["grahas"]["Moon"]["longitude"] == own["grahas"]["Moon"]["longitude"]
