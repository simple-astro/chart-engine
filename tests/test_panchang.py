"""Panchang and transit tests."""
from datetime import date, datetime, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.panchang import compute_panchang
from core.transits import transit_positions

# New Delhi.
LAT, LON, TZ = 28.6139, 77.2090, "Asia/Kolkata"


def test_sunrise_before_sunset_on_the_date():
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    assert p.sunrise < p.sunset
    # Both fall on the civil date in local time.
    assert p.sunrise.astimezone(p.tz).date() == date(2000, 1, 1)


def test_tithi_in_range_and_paksha_consistent():
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    assert 1 <= p.tithi_number <= 30
    if p.tithi_number <= 15:
        assert p.paksha == "Shukla"
    else:
        assert p.paksha == "Krishna"


def test_nakshatra_matches_moon_at_sunrise():
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    jd = julian_day(p.sunrise)
    g = compute_grahas(jd, "krishnamurti", node_type="mean")
    assert p.nakshatra_index == g["Moon"].nakshatra_index


def test_yoga_and_karana_in_range():
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    assert 1 <= p.yoga_number <= 27
    assert 1 <= p.karana_number <= 60


def test_weekday_and_rahu_kalam_segment_for_saturday():
    # 2000-01-01 was a Saturday; Rahu Kalam is the 3rd of 8 daytime segments.
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    assert p.weekday == "Saturday"
    seg = (p.sunset - p.sunrise) / 8
    expected_start = p.sunrise + seg * 2   # 3rd segment (0-indexed 2)
    assert abs((p.rahu_kalam[0] - expected_start).total_seconds()) < 1.0
    assert abs((p.rahu_kalam[1] - p.rahu_kalam[0] - seg).total_seconds()) < 1.0


def test_rahu_kalam_within_daytime():
    p = compute_panchang(date(2000, 1, 1), LAT, LON, TZ)
    assert p.sunrise <= p.rahu_kalam[0] < p.rahu_kalam[1] <= p.sunset


def test_transit_positions_match_grahas():
    dt = datetime(2020, 3, 20, 12, 0, tzinfo=timezone.utc)
    t = transit_positions(dt, "krishnamurti", node_type="mean")
    g = compute_grahas(julian_day(dt), "krishnamurti", node_type="mean")
    assert set(t) == set(g)
    assert abs(t["Sun"].longitude - g["Sun"].longitude) < 1e-9
    diff = (t["Ketu"].longitude - t["Rahu"].longitude) % 360.0
    assert abs(diff - 180.0) < 1e-9
