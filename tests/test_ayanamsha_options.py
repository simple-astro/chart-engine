"""Every ayanamsha offered in the form computes a chart; Tropical has none at all."""
import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from app.main import app

Q = {"name": "t", "dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


@pytest.mark.parametrize("ay, value", [("krishnamurti", 23.588), ("lahiri", 23.685), ("pushya", 22.545),
                                       ("raman", 22.238), ("fagan", 24.568), ("tropical", 0.0)])
def test_each_ayanamsha(ay, value):
    c = TestClient(app).post("/chart", json={**Q, "ayanamsha": ay}).json()
    assert abs(c["meta"]["ayanamsha_value"] - value) < 0.01


def test_tropical_matches_plain_tropical_positions():
    c = TestClient(app).post("/chart", json={**Q, "ayanamsha": "tropical"}).json()
    jd = c["meta"]["julian_day"]
    assert abs(c["grahas"]["Sun"]["longitude"] - swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]) < 0.01
    assert abs(c["lagna"]["ascendant"] - swe.houses(jd, Q["lat"], Q["lon"], b"P")[1][0]) < 0.01
