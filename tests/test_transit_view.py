"""Transits tab: sky on a date over the natal chart, with the running dasha and alignment notes."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

BIRTH = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def pid(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    return c, c.post("/profiles", json=BIRTH).json()["id"]


def test_overlay_for_a_date(pid):
    c, i = pid
    r = c.get(f"/profiles/{i}/transit?date=2026-10-08").json()
    assert [d["lord"] for d in r["dasha"]] == ["Venus", "Mercury", "Mercury"]
    p = {x["planet"]: x for x in r["planets"]}
    assert len(p) == 9 and p["Saturn"]["sign"] == "Pisces" and p["Saturn"]["h_lagna"] == 4 and p["Saturn"]["h_moon"] == 5
    assert p["Jupiter"]["sign"] == "Cancer" and p["Venus"]["dasha"] == "Mahadasha"
    assert p["Mercury"]["dasha"] == "Antardasha and Pratyantar"
    assert any("Jupiter is 9th from your Moon" in n["text"] for n in r["notes"])
    assert r["moon_today"]["tara"]


def test_sade_sati_shows_up_when_saturn_crosses_the_moon_sign(pid):
    c, i = pid
    r = c.get(f"/profiles/{i}/transit?date=2015-06-01").json()  # Saturn in Scorpio over natal Moon
    assert any(n["kind"] == "care" and "Sade Sati" in n["text"] and "peak" in n["text"] for n in r["notes"])


def test_bad_dates_and_default(pid):
    c, i = pid
    assert c.get(f"/profiles/{i}/transit?date=2026-13-01").status_code == 422
    assert c.get(f"/profiles/{i}/transit?date=1800-01-01").status_code == 422
    assert c.get(f"/profiles/{i}/transit").json()["planets"]
