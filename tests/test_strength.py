"""Ashtakavarga and lord exchange (parivartana)."""
import random

from fastapi.testclient import TestClient

from app.main import app
from core.ashtakavarga import PLANETS, ashtakavarga
from core.parivartana import exchanges, lord_placements

ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO, LIBRA, SCORPIO, SAG, CAP, AQU, PISCES = range(12)
BASE = {"Sun": ARIES, "Moon": ARIES, "Mars": ARIES, "Mercury": ARIES, "Jupiter": ARIES, "Venus": ARIES,
        "Saturn": ARIES, "Rahu": ARIES, "Ketu": LIBRA}


def test_bav_totals_are_fixed_for_any_chart():
    rng = random.Random(7)
    for _ in range(50):
        signs = {p: rng.randrange(12) for p in BASE}
        a = ashtakavarga(signs, rng.randrange(12))
        assert a["bav_totals"] == {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54, "Jupiter": 56,
                                   "Venus": 52, "Saturn": 39}
        assert a["sav_total"] == 337 == sum(a["sav"])


def test_bindus_counted_from_each_contributor():
    a = ashtakavarga(BASE, ARIES)
    # Everything in Aries: Sun gets a bindu in Aries only from Sun, Mars and Saturn (1st place).
    assert a["bav"]["Sun"][ARIES] == 3
    assert a["own_bindus"]["Sun"] == 3
    # Jupiter's 11th place is benefic from every contributor except Saturn.
    assert a["bav"]["Jupiter"][AQU] == 7
    assert set(a["own_bindus"]) == set(PLANETS)


def test_exchange_types():
    maha = exchanges({**BASE, "Sun": CANCER, "Moon": LEO}, ARIES)
    assert maha == [{"planets": ["Sun", "Moon"], "houses": [4, 5], "type": "Maha", "signs": [CANCER, LEO]}]
    assert exchanges({**BASE, "Mars": GEMINI, "Mercury": ARIES}, ARIES)[0]["type"] == "Khala"
    assert exchanges({**BASE, "Jupiter": CAP, "Saturn": PISCES}, ARIES)[0]["type"] == "Dainya"
    assert exchanges(BASE, ARIES) == []  # Mars in its own sign is not an exchange


def test_lord_placements():
    rows = lord_placements({**BASE, "Venus": CANCER}, ARIES)
    assert rows[1] == {"house": 2, "sign_index": TAURUS, "lord": "Venus", "lord_in": 4}
    assert rows[0]["lord"] == "Mars" and rows[0]["lord_in"] == 1


def test_chart_includes_strength_data():
    r = TestClient(app).post("/chart", json={"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629,
                                             "lon": 76.7884, "tz_name": "Asia/Kolkata"})
    c = r.json()
    assert c["ashtakavarga"]["sav_total"] == 337 and len(c["lords"]) == 12
    assert set(c["exchanges"]) == {"D1", "D9"}


def test_dignity_rules():
    from core.dignity import dignity
    assert dignity("Moon", SCORPIO) == "debilitated" and dignity("Moon", TAURUS) == "exalted"
    assert dignity("Moon", CANCER) == "own" and dignity("Sun", LEO) == "own"
    assert dignity("Venus", LEO) == "enemy" and dignity("Mars", LEO) == "friendly"


def test_chat_context_is_synthesised():
    import json
    from app import ask
    c = TestClient(app).post("/chart", json={"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629,
                                             "lon": 76.7884, "tz_name": "Asia/Kolkata"}).json()
    ctx = ask.llm_context({"chart": c, "request": {"name": "Sukh"}})
    d = json.loads(ctx)
    assert d["planets"]["Moon"]["dignity"] == "debilitated" and d["planets"]["Moon"]["neecha_bhanga"].startswith("cancelled")
    assert set(d["houses"]) == {str(h) for h in range(1, 13)} and d["dasha"]["maha"]["lord"]
    assert len(ctx) < 9000  # compressed: well under the old ~15k-character raw dump
