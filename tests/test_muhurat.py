"""Daily muhurat rules and endpoint."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import muhurat
from app.main import app

DELHI = {"lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


def _p(**kw):
    """A fake panchang day: Thursday, Shukla 5th, Pushya, a neutral yoga and karana."""
    rise = datetime(2026, 1, 1, 1, 30, tzinfo=timezone.utc)
    base = dict(weekday="Thursday", tithi_number=5, tithi_paksha_index=5, paksha="Shukla", nakshatra_index=7,
                nakshatra="Pushya", yoga_number=2, yoga="Priti", karana="Bava", moon_sign_index=3,
                sunrise=rise, sunset=rise + timedelta(hours=11), rahu_kalam=(rise, rise), yamaganda=(rise, rise),
                gulika=(rise, rise))
    return NS(**{**base, **kw})


def _act(key, p, birth_nak=None, birth_moon=None):
    a = next(x for x in muhurat.ACTIVITIES if x["key"] == key)
    return muhurat.judge(a, p, muhurat.day_factors(p, birth_nak, birth_moon))


def test_good_day_for_buying_gold():
    r = _act("gold", _p())
    assert r["verdict"] == "excellent" and r["label"] == "Very good"


def test_amavasya_and_bhadra_pull_a_day_down():
    assert _act("gold", _p(tithi_number=30, tithi_paksha_index=15, paksha="Krishna"))["verdict"] in ("avoid", "fair")
    assert _act("start", _p(karana="Vishti"))["score"] == _act("start", _p())["score"] - 2


def test_rikta_tithi_and_harsh_nakshatra():
    r = _act("travel", _p(tithi_paksha_index=9, tithi_number=9, nakshatra_index=17, nakshatra="Jyeshtha"))
    assert r["verdict"] == "avoid"
    assert any("Rikta" in w["text"] for w in r["why"]) and any("harsh" in w["text"] for w in r["why"])


def test_marriage_prefers_waxing_moon():
    shukla = _act("marriage", _p(nakshatra_index=3, nakshatra="Rohini"))
    late_krishna = _act("marriage", _p(nakshatra_index=3, nakshatra="Rohini", paksha="Krishna",
                                       tithi_number=26, tithi_paksha_index=11))
    assert shukla["score"] - late_krishna["score"] == 3
    assert "astrologer" in shukla["note"]


def test_tara_and_chandra_bala():
    f = muhurat.day_factors(_p(nakshatra_index=6, moon_sign_index=3), birth_nak=0, birth_moon_sign=8)
    assert f["tara"]["name"] == "Naidhana"           # Punarvasu is the 7th star from Ashwini
    assert muhurat.day_factors(_p(nakshatra_index=7), 0, None)["tara"]["name"] == "Mitra"  # 8th
    assert f["chandra"]["house"] == 8 and f["chandra"]["score"] == -2  # Chandrashtama
    # personal factors can lift a day by at most one step
    good = muhurat.day_factors(_p(nakshatra_index=7, moon_sign_index=3), birth_nak=6, birth_moon_sign=3)
    assert good["tara"]["score"] + good["chandra"]["score"] == 2
    assert _act("gold", _p(), 6, 3)["score"] == _act("gold", _p())["score"] + 1


def test_travel_mentions_disha_shool():
    assert "south" in _act("travel", _p())["note"]  # Thursday


def test_choghadiya_and_abhijit():
    w = muhurat.windows(_p(weekday="Sunday"))
    assert [c["name"] for c in w["choghadiya"]][:3] == ["Udveg", "Chal", "Labh"] and len(w["choghadiya"]) == 8
    assert w["abhijit"] is not None
    assert muhurat.windows(_p(weekday="Wednesday"))["abhijit"] is None


def test_endpoint_returns_a_week(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    r = c.post("/muhurat", json={**DELHI, "start": "2026-10-07", "days": 7, "birth_nakshatra": 17,
                                 "birth_moon_sign": 7})
    assert r.status_code == 200
    days = r.json()["days"]
    assert len(days) == 7 and len(days[0]["activities"]) == len(muhurat.ACTIVITIES)
    assert days[3]["tithi"]["name"] == "Amavasya" and days[3]["overall"]["verdict"] == "avoid"
    assert days[0]["tara"]["name"] and days[0]["windows"]["choghadiya"]
    assert c.post("/muhurat", json={**DELHI, "start": "2026-10-07", "days": 30}).status_code == 422
    assert c.post("/muhurat", json={**DELHI, "tz_name": "Not/AZone", "start": "2026-10-07"}).status_code == 422


@pytest.mark.parametrize("n,s", [(1, "1st"), (2, "2nd"), (3, "3rd"), (11, "11th"), (12, "12th"), (13, "13th"), (14, "14th")])
def test_ordinal(n, s):
    assert muhurat._ordinal(n) == s
