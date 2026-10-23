"""The free daily panchang image (app/daily_panchang.py): Lahiri times that match Drik Panchang, festivals,
good times that never overlap the times to avoid, and open to everyone without signing in."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import daily_panchang as D
from app.main import app


def test_matches_drik_panchang_for_new_delhi():
    p = D.panchang_for(date(2026, 10, 23))  # Drik Panchang, New Delhi: Dwadashi till 2:35 PM, P.Bhadrapada till 9:02 PM
    assert p["tithi"] == ("Shukla Dwadashi", "till 2:36 PM")
    assert p["nakshatra"] == ("Purva Bhadrapada", "till 9:03 PM")   # Lahiri: KP would say 8:52 PM
    assert p["yoga"] == ("Dhruva", "till 10:08 PM") and p["karana"][0] == "Balava"
    assert p["avoid"][0] == ("Rahu Kalam", "10:40 AM – 12:05 PM")
    assert "Shukra Pradosh Vrat" in p["festivals"] and p["month"][0] == "Ashwin, Shukla"


def test_festival_days():
    assert "Holika Dahan" in D.panchang_for(date(2026, 3, 3))["festivals"]     # Bhadra on the 2nd's evening
    assert "Holika Dahan" not in D.panchang_for(date(2026, 3, 2))["festivals"]
    assert D.panchang_for(date(2026, 11, 8))["festivals"][0].startswith("Diwali")
    f = D.panchang_for(date(2026, 11, 24))["festivals"]
    assert "Kartik Purnima" in f and "Prakash Purab, Guru Nanak Dev Ji" in f


def test_good_times_never_overlap_the_times_to_avoid():
    p = D.panchang_for(date(2026, 10, 22))   # Amrit Choghadiya falls exactly on Rahu Kalam that Thursday
    assert not any("Amrit" in k for k, _ in p["good"]) and len(p["good"]) <= 4


def test_all_the_elements_and_the_days_advice():
    p = D.panchang_for(date(2026, 10, 23))
    assert p["moon_sign"] == ("Kumbha", "Aquarius") and p["sun_sign"] == ("Tula", "Libra")
    assert p["moonrise"].endswith("PM") and p["ayana"] == "Dakshinayana" and "Shaka 1948" in p["samvat"]
    assert p["do"][0].startswith("Venus’s day") and any("Pradosh" in x for x in p["do"]) and len(p["do"]) == 3
    assert any("Disha Shool" in x and "west" in x for x in p["dont"])
    d = D.panchang_for(date(2026, 11, 8))
    assert d["do"][0].startswith("Diwali:") and any("Rikta" in x for x in d["dont"])      # Chaturdashi at sunrise
    assert any(x.startswith("Bhadra till 10:05 AM") for x in D.panchang_for(date(2026, 11, 24))["dont"])


def test_thought_for_today():
    from app import daily_thoughts as T
    assert D.panchang_for(date(2026, 11, 8))["thought"][1] == "Diwali"                    # the festival first
    assert D.panchang_for(date(2026, 10, 22))["thought"][1].startswith("Ekadashi")         # then the vrat tithi
    assert D.panchang_for(date(2026, 10, 31))["thought"][1] == "Ardra Nakshatra · Rudra, the storm"
    from core.constants import NAKSHATRAS
    assert set(T.NAKSHATRA) == set(NAKSHATRAS)
    assert all(len(line) <= 90 for line, *_ in [*T.NAKSHATRA.values(), *T.TITHI.values()] + [f[1:] for f in T.FESTIVAL])


def test_the_image():
    png = D.card(date(2026, 11, 8))
    from PIL import Image
    import io
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and Image.open(io.BytesIO(png)).size == (1080, 1920)


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")


def test_open_without_signing_in_but_the_api_stays_private(gated):
    c = TestClient(app)
    r = c.get("/panchang/today.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and "max-age" in r.headers["cache-control"]
    assert c.get("/panchang/2026-11-08.png").status_code == 200
    page = c.get("/panchang?d=2026-11-08")
    assert page.status_code == 200 and "Download image" in page.text and 'og:image' in page.text
    assert c.get("/panchang/1990-01-01.png").status_code == 404          # a year either side only
    assert c.post("/panchang", json={"on": "2026-11-08", "lat": 28.6, "lon": 77.2, "tz_name": "Asia/Kolkata"}).status_code == 401
