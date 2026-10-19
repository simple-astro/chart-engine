"""Marriage muhurat hard exclusions (app/muhurat_rules.py): each rule, real 2026-27 dates, and the finder's order."""
from datetime import date

import pytest

from app import muhurat, muhurat_rules as R
from core.panchang import compute_panchang

DELHI = (28.6139, 77.209, "Asia/Kolkata")
# An open day: Margashira Shukla 5, Sun in Scorpio, Jupiter and Venus well away from the Sun.
OPEN = {"tithi": 5, "paksha_index": 5, "month": 8, "adhik": False, "sun_sign": 7, "jupiter_sep": 90.0,
        "venus_sep": 40.0}


def _keys(**kw):
    return [e["key"] for e in R.exclusions("marriage", {**OPEN, **kw})]


def test_open_day_has_no_exclusions():
    assert _keys() == []


@pytest.mark.parametrize("tithi,key", [(4, "rikta"), (9, "rikta"), (14, "rikta"), (19, "rikta"), (24, "rikta"),
                                       (29, "rikta"), (8, "ashtami"), (23, "ashtami"), (30, "amavasya")])
def test_tithi_exclusions(tithi, key):
    assert _keys(tithi=tithi, paksha_index=tithi if tithi <= 15 else tithi - 15) == [key]


def test_amavasya_is_not_also_counted_as_rikta():
    assert _keys(tithi=30, paksha_index=15) == ["amavasya"]


@pytest.mark.parametrize("month,tithi,closed", [
    (3, 10, False), (3, 11, True), (3, 25, True),        # Ashadha: from Devshayani Ekadashi (Shukla 11)
    (4, 1, True), (5, 20, True), (6, 5, True),           # Shravana, Bhadrapada, Ashwayuja: all of them
    (7, 10, True), (7, 11, False), (7, 12, False),       # Kartika: up to Dev Uthani Ekadashi
    (8, 1, False)])
def test_chaturmas(month, tithi, closed):
    assert ("chaturmas" in _keys(month=month, tithi=tithi, paksha_index=(tithi - 1) % 15 + 1)) is closed


def test_adhik_maas():
    assert "adhik" in _keys(adhik=True)


def test_pitru_paksha_is_the_dark_half_of_bhadrapada():
    assert "pitru_paksha" in _keys(month=5, tithi=16, paksha_index=1)
    assert "pitru_paksha" not in _keys(month=5, tithi=12, paksha_index=12)


@pytest.mark.parametrize("sun,closed", [(8, True), (11, True), (9, False), (0, False)])
def test_kharmas(sun, closed):
    assert ("kharmas" in _keys(sun_sign=sun)) is closed


def test_holashtak():
    assert "holashtak" in _keys(month=11, tithi=10, paksha_index=10)
    assert "holashtak" not in _keys(month=11, tithi=7, paksha_index=7)
    assert "holashtak" not in _keys(month=11, tithi=16, paksha_index=1)


def test_guru_and_shukra_asta():
    assert "guru_asta" in _keys(jupiter_sep=5.0) and "guru_asta" not in _keys(jupiter_sep=12.0)
    assert "shukra_asta" in _keys(venus_sep=5.0) and "shukra_asta" not in _keys(venus_sep=11.0)


def test_other_activities_are_not_affected():
    assert R.exclusions("gold", {**OPEN, "month": 4}) == []


def _facts(d):
    return R.facts(compute_panchang(d, *DELHI))


@pytest.mark.parametrize("d,key", [
    (date(2026, 5, 25), "adhik"),          # Adhik Jyeshtha, 17 May - 15 Jun 2026
    (date(2026, 8, 15), "chaturmas"),
    (date(2026, 10, 1), "pitru_paksha"),   # 26 Sep - 10 Oct 2026
    (date(2026, 12, 25), "kharmas"),       # Sun in Sagittarius
    (date(2027, 3, 18), "holashtak"),      # before Holi, 22 Mar 2027
    (date(2026, 7, 28), "guru_asta"),      # Jupiter's conjunction with the Sun, late July 2026
    (date(2026, 10, 24), "shukra_asta"),   # Venus's inferior conjunction, late October 2026
])
def test_real_calendar_periods(d, key):
    assert key in [e["key"] for e in R.exclusions("marriage", _facts(d))]


def test_the_dark_half_of_kartika_after_dev_uthani_is_open():
    f = _facts(date(2026, 12, 3))
    assert f["month"] == 7 and f["tithi"] > 15 and not f["adhik"]  # Kartika Krishna (amanta)
    assert not {"chaturmas", "kharmas", "adhik"} & {e["key"] for e in R.exclusions("marriage", f)}


def test_reported_dates_are_no_longer_very_good():
    """QA: 19 Oct 2026 (Shukla Ashtami, Chaturmas) and 11 Nov 2026 (Chaturmas) were rated 'Very good'."""
    for d in (date(2026, 10, 19), date(2026, 11, 11)):
        day = muhurat.muhurat_days(d, 1, *DELHI)[0]
        m = next(a for a in day["activities"] if a["key"] == "marriage")
        assert m["verdict"] == "avoid" and any("Chaturmas" in r for r in m["excluded"])
        assert any(w.get("hard") and "Chaturmas" in w["text"] for w in m["why"])  # the reason is shown


def test_finder_skips_excluded_days_and_says_why():
    r = muhurat.find_dates("marriage", date(2026, 10, 19), 30, *DELHI)
    assert r["dates"] == []
    assert any("Chaturmas" in s["reason"] and s["days"] == 30 for s in r["skipped"])


def test_is_today_good_for_marriage_row_uses_the_exclusions(tmp_path, monkeypatch):
    """Today › "Is today good for…" reads POST /muhurat."""
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    r = TestClient(app).post("/muhurat", json={"lat": DELHI[0], "lon": DELHI[1], "tz_name": DELHI[2],
                                               "start": "2026-10-19", "days": 1})
    m = next(a for a in r.json()["days"][0]["activities"] if a["key"] == "marriage")
    assert m["label"] == "Better to avoid" and m["excluded"]


def test_finder_sorts_by_rating_then_date(monkeypatch):
    def day(d, score, verdict):
        a = {"key": "gold", "score": score, "verdict": verdict, "label": "", "why": [], "note": None, "excluded": []}
        w = {"abhijit": None, "choghadiya": [], "rahu_kalam": [], "yamaganda": [], "gulika": []}
        return {"date": d, "weekday": "", "activities": [a], "tithi": {"name": ""}, "nakshatra": "", "windows": w}
    days = [day("2026-12-05", 5, "excellent"), day("2026-12-01", 3, "excellent"), day("2026-12-02", 1, "good"),
            day("2026-12-03", 4, "excellent")]
    monkeypatch.setattr(muhurat, "muhurat_days", lambda *a, **k: days)
    r = muhurat.find_dates("gold", date(2026, 12, 1), 5, *DELHI)
    assert [x["date"] for x in r["dates"]] == ["2026-12-01", "2026-12-03", "2026-12-05", "2026-12-02"]
    assert r["order"] == "rating, then date"
