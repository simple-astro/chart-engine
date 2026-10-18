"""Avakhada chakra, special points and lagna rising times."""
from datetime import date

from fastapi.testclient import TestClient

from app import birth_extras as B
from app.main import app

REQ = {"name": "t", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata",
       "ayanamsha": "krishnamurti"}


def test_avakhada_and_special_points():
    d = TestClient(app).post("/birth-extras", json=REQ).json()
    a = {r["label"]: r["value"] for r in d["avakhada"]["rows"]}
    assert a["Naming letter"] == "No" and a["Gana"] == "Rakshasa" and a["Nadi"] == "Adi" and a["Yoni"] == "Deer"
    assert a["Paya"].startswith("Iron") and a["Birth day (Vedic)"] == "Tuesday" and a["Tithi at birth"] == "Shukla 8th"
    p = {x["name"]: x for x in d["special"]["points"]}
    assert p["Indu Lagna"]["sign"] == "Leo"                       # kalas 30 + 16 = 46 -> 10th from a Scorpio Moon
    assert p["Bhrigu Bindu"]["sign"] == "Cancer" and abs(p["Bhrigu Bindu"]["degrees_in_sign"] - 13.81) < 0.05
    assert {"Bhava Lagna", "Hora Lagna", "Ghati Lagna", "Mandi", "Gulika"} <= set(p)


def test_each_lagna_rises_once_and_the_day_is_covered():
    r = B.lagna_times(date(2026, 10, 18), 49.8954, -97.1385, "America/Winnipeg")
    assert r[0]["start"] == "00:00" and r[-1]["end"] == "24:00" and len(r) in (12, 13)
    assert all(a["end"] == b["start"] for a, b in zip(r, r[1:]))
    assert TestClient(app).get("/lagna-times", params={"lat": 49.9, "lon": -97.1, "tz": "Mars/Base"}).status_code == 422
