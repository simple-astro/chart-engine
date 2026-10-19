"""Paryaya: transiting Jupiter and Saturn over natal points (core/paryaya.py)."""
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from core import paryaya
from core.ephemeris import julian_day
from core.grahas import compute_grahas

MODI = {"name": "Modi", "dob": "1950-09-17", "tob": "11:00:00", "lat": 23.7869, "lon": 72.6385,
        "tz_name": "Asia/Kolkata", "ayanamsha": "lahiri"}


def test_each_crossing_is_on_the_natal_degree():
    c = TestClient(app).post("/chart", json=MODI).json()
    xs = paryaya.crossings(c, date(2024, 1, 1), date(2027, 1, 1))
    assert xs and {x["planet"] for x in xs} <= {"Jupiter", "Saturn"}
    pts = paryaya.natal_points(c)
    for x in xs:
        d = date.fromisoformat(x["date"])
        jd = julian_day(datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc))
        lon = compute_grahas(jd, "lahiri")[x["planet"]].longitude
        assert abs((lon - pts[x["point"]] + 180) % 360 - 180) < 0.6   # within a day's motion of the exact degree
    assert [x["date"] for x in xs] == sorted(x["date"] for x in xs)


def test_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=MODI).json()["id"]
    r = c.get(f"/profiles/{pid}/paryaya").json()
    assert r["from"] < r["today"] < r["to"] and all(r["from"] <= x["date"] <= r["to"] for x in r["crossings"])
