"""Behavioural tests for lagna (ascendant) and house cusps."""
from datetime import datetime, timezone

from core.ephemeris import julian_day
from core.houses import compute_houses

# New Delhi, a fixed instant.
JD = julian_day(datetime(1990, 8, 15, 6, 30, tzinfo=timezone.utc))
LAT, LON = 28.6139, 77.2090


def test_twelve_cusps_returned():
    h = compute_houses(JD, LAT, LON, "krishnamurti")
    assert len(h.cusps) == 12
    assert 0 <= h.ascendant < 360.0


def test_kp_mode_uses_placidus_and_cusp1_is_ascendant():
    h = compute_houses(JD, LAT, LON, "krishnamurti")
    assert h.house_system == "placidus"
    # In Placidus the 1st cusp coincides with the ascendant.
    assert abs((h.cusps[0].longitude - h.ascendant + 180) % 360 - 180) < 1e-6


def test_classical_mode_uses_whole_sign():
    h = compute_houses(JD, LAT, LON, "lahiri")
    assert h.house_system == "whole_sign"
    # First cusp is the very start of the ascendant's sign.
    asc_sign_start = (int(h.ascendant // 30)) * 30.0
    assert abs(h.cusps[0].longitude - asc_sign_start) < 1e-9
    # Whole-sign cusps are exactly 30 apart and each sits at a sign boundary.
    for i, cusp in enumerate(h.cusps):
        assert abs(cusp.longitude - (asc_sign_start + 30 * i) % 360.0) < 1e-9
        assert cusp.degrees_in_sign == 0.0


def test_each_cusp_has_consistent_sign():
    h = compute_houses(JD, LAT, LON, "krishnamurti")
    for cusp in h.cusps:
        assert cusp.sign_index == int(cusp.longitude // 30)
        assert 0 <= cusp.sign_index <= 11
