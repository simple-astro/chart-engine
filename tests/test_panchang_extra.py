"""The fuller panchang on the Muhurat screen: limb end times, lords and deities, the year, month and season,
checked against a published panchang (Divya Chakshu, Bhopal, 18 Oct 2026) and the 2026 Ugadi."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import panchang_extra as X
from app.main import app
from core.panchang import compute_panchang

BHOPAL = (23.2599, 77.4126, "Asia/Kolkata")


def _day(d: date):
    return compute_panchang(d, *BHOPAL), compute_panchang(d + timedelta(days=1), *BHOPAL)


def _details(d: date) -> dict:
    p, nxt = _day(d)
    return X.details(p, nxt.sunrise)


def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(ZoneInfo("Asia/Kolkata"))


def test_limb_end_times_match_a_published_panchang():
    p, _ = _day(date(2026, 10, 18))
    e = X.limb_ends(p.sunrise)
    # Tithi and karana do not depend on the ayanamsa: within a minute of the published 08:29
    for k in ("tithi", "karana"):
        assert abs((_local(e[k]["ends"]) - datetime(2026, 10, 18, 8, 29, 10, tzinfo=ZoneInfo("Asia/Kolkata"))).total_seconds()) < 60
    assert (e["tithi"]["name"], e["tithi"]["next"]) == ("Shukla 7th", "Shukla 8th")
    assert (e["karana"]["name"], e["karana"]["next"]) == ("Vanija", "Vishti")
    # Nakshatra and yoga: KP here, Lahiri there (about 6′ apart), so 10–20 minutes earlier, same names
    assert e["nakshatra"]["name"] == "Purva Ashadha" and _local(e["nakshatra"]["ends"]).hour == 12
    assert e["yoga"]["name"] == "Sukarma" and _local(e["yoga"]["ends"]).hour == 23


def test_lords_deities_year_month_and_season():
    p, nxt = _day(date(2026, 10, 18))
    d = X.details(p, nxt.sunrise)
    assert (d["nakshatra_lord"], d["nakshatra_deity"]) == ("Venus", "Apa")
    assert (d["tithi_lord"], d["tithi_deity"]) == ("Saturn", "Surya")
    assert (d["samvatsara"], d["lunar_month"], d["solar_month"]) == ("Parabhava", "Ashwayuja", "Libra")
    assert d["ritu"].startswith("Sharad") and d["naming"]["letters"] == ["Bhu", "Dha", "Pha", "Dha"]
    assert len(d["horas"]) == 24 and d["horas"][0]["lord"] == "Sun"                 # Sunday's first hora
    # Ugadi 2026 (19 March): the year and month turn over
    before, after = _details(date(2026, 3, 18)), _details(date(2026, 3, 20))
    assert (before["samvatsara"], before["lunar_month"]) == ("Vishvavasu", "Phalguna")
    assert (after["samvatsara"], after["lunar_month"]) == ("Parabhava", "Chaitra")
    assert _details(date(2026, 1, 15))["samvatsara"] == "Vishvavasu"


def test_muhurat_endpoint_carries_the_full_panchang(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    r = TestClient(app).post("/muhurat", json={"start": "2026-10-18", "days": 2, "lat": 23.26, "lon": 77.41,
                                               "tz_name": "Asia/Kolkata"})
    assert r.status_code == 200
    day = r.json()["days"][0]
    assert set(day["ends"]) == {"tithi", "nakshatra", "yoga", "karana"} and day["panchang"]["samvatsara"] == "Parabhava"
