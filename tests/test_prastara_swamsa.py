"""Prastharashtakavarga (which source gives each bindu) and the Karakamsa / Swamsa charts, checked against the
AstroSage report for the same birth (1 Sep 1987, 14:20:17, Chandigarh, Lahiri)."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
REQ = {"name": "Sunny", "place": "Chandigarh", "dob": "1987-09-01", "tob": "14:20:17", "lat": 30 + 44 / 60,
       "lon": 76 + 47 / 60, "tz_name": "Asia/Kolkata", "node_type": "mean", "ayanamsha": "lahiri"}
# AstroSage's Prastharashtakavarga for the Sun and the Moon, by sign from Aries
ASTROSAGE = {
    "Sun": {"Sun": "111011010011", "Moon": "100011000100", "Mars": "111011010011", "Mercury": "111100101100",
            "Jupiter": "000011001010", "Venus": "000100000110", "Saturn": "011111011010", "Lagna": "010001110011"},
    "Moon": {"Sun": "011000100111", "Moon": "110011010100", "Mars": "111001101100", "Mercury": "011010111011",
             "Jupiter": "100100110111", "Venus": "111000111010"},
}


def _chart() -> dict:
    return TestClient(app).post("/chart", json=REQ).json()


def test_prastara_matches_astrosage_and_adds_up_to_the_bav():
    a = _chart()["ashtakavarga"]
    for planet, rows in ASTROSAGE.items():
        for src, bits in rows.items():
            assert "".join(map(str, a["prastara"][planet][src])) == bits, (planet, src)
    for planet, grid in a["prastara"].items():
        assert [sum(col) for col in zip(*grid.values())] == a["bav"][planet]


def test_karakamsa_is_the_atmakaraka_navamsa_and_both_charts_are_drawn():
    c = _chart()
    j = c["jaimini"]
    assert j["atmakaraka"]["planet"] == "Mercury" and j["karakamsa"]["sign"] == "Scorpio"
    assert c["vargas"]["D9"]["Mercury"]["sign_index"] == 7
    html = (STATIC / "index.html").read_text()
    assert "Karakamsa and Swamsa charts" in html and "id=\"jaikk\"" in html and "id=\"jaisw\"" in html
    assert "Prastharashtakavarga" in (STATIC / "strength.js").read_text()
