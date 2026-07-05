"""Independently-verifiable astronomical anchors.

These assert values I can reason about without external software, so they catch
real logic bugs (not just regressions). Golden-master snapshot tests live in
test_reference_charts.py.
"""
import swisseph as swe

from core.ephemeris import julian_day, get_ayanamsha
from datetime import datetime, timezone


def test_kp_ayanamsha_at_j2000():
    # Verified directly against pyswisseph 2.10.03: SIDM_KRISHNAMURTI @ 2000-01-01 12:00 UT
    jd = julian_day(datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc))
    assert abs(get_ayanamsha(jd, "krishnamurti") - 23.760240) < 1e-4


def test_lahiri_ayanamsha_at_j2000():
    jd = julian_day(datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc))
    assert abs(get_ayanamsha(jd, "lahiri") - 23.857092) < 1e-4


def test_julian_day_j2000():
    jd = julian_day(datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc))
    assert abs(jd - 2451545.0) < 1e-6
