"""Divisional chart (varga) tests with classical Parasari anchors."""
from datetime import datetime, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.vargas import varga_sign, compute_vargas, VARGA_DIVISIONS

JD = julian_day(datetime(1990, 8, 15, 6, 30, tzinfo=timezone.utc))
G = compute_grahas(JD, "krishnamurti", node_type="mean")


def test_d1_is_the_rashi():
    assert varga_sign(0.0, 1) == 0        # Aries
    assert varga_sign(95.0, 1) == 3       # Cancer (90-120)


def test_navamsha_d9_anchors():
    # Continuous navamsha: Aries starts at Aries; Taurus (fixed) starts at Capricorn.
    assert varga_sign(0.0, 9) == 0        # start of Aries -> Aries
    assert varga_sign(3.4, 9) == 1        # 2nd navamsha of Aries -> Taurus
    assert varga_sign(30.0, 9) == 9       # start of Taurus -> Capricorn


def test_hora_d2_anchors():
    # Odd sign (Aries): first half Leo, second half Cancer. Even sign (Taurus) reversed.
    assert varga_sign(5.0, 2) == 4        # Aries 0-15 -> Leo
    assert varga_sign(20.0, 2) == 3       # Aries 15-30 -> Cancer
    assert varga_sign(35.0, 2) == 3       # Taurus 0-15 -> Cancer


def test_drekkana_d3_anchors():
    assert varga_sign(5.0, 3) == 0        # Aries 0-10 -> Aries
    assert varga_sign(15.0, 3) == 4       # Aries 10-20 -> Leo (5th)
    assert varga_sign(25.0, 3) == 8       # Aries 20-30 -> Sagittarius (9th)


def test_trimshamsha_d30_anchors():
    # Odd sign Aries: Mars 0-5, Saturn 5-10, Jupiter 10-18, Mercury 18-25, Venus 25-30.
    assert varga_sign(3.0, 30) == 0       # Mars -> Aries
    assert varga_sign(7.0, 30) == 10      # Saturn -> Aquarius
    assert varga_sign(15.0, 30) == 8      # Jupiter -> Sagittarius
    # Even sign Taurus: Venus 0-5, Mercury 5-12, Jupiter 12-20, Saturn 20-25, Mars 25-30.
    assert varga_sign(33.0, 30) == 1      # Venus -> Taurus


def test_all_sixteen_vargas_present_and_valid():
    v = compute_vargas(G)
    assert set(v) == {f"D{n}" for n in VARGA_DIVISIONS}
    assert len(VARGA_DIVISIONS) == 16
    for chart in v.values():
        assert set(chart) == set(G)
        for placement in chart.values():
            assert 0 <= placement["sign_index"] <= 11
