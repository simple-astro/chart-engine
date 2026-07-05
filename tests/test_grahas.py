"""Behavioural tests for graha (planet) computation."""
from datetime import datetime, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas


# A fixed reference instant (UT) used across graha tests.
JD = julian_day(datetime(1990, 8, 15, 6, 30, tzinfo=timezone.utc))


def test_all_nine_grahas_present():
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    assert set(g) == {
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"
    }


def test_ketu_exactly_opposite_rahu():
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    diff = (g["Ketu"].longitude - g["Rahu"].longitude) % 360.0
    assert abs(diff - 180.0) < 1e-9


def test_rahu_is_retrograde_by_convention():
    # The lunar node moves retrograde; Rahu (and Ketu) flagged retrograde.
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    assert g["Rahu"].retrograde is True
    assert g["Ketu"].retrograde is True


def test_longitude_maps_to_correct_sign_and_degrees():
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    for graha in g.values():
        assert 0 <= graha.longitude < 360.0
        assert 0 <= graha.sign_index <= 11
        assert graha.sign_index == int(graha.longitude // 30)
        assert abs(graha.degrees_in_sign - (graha.longitude % 30.0)) < 1e-9


def test_nakshatra_and_pada_in_range():
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    for graha in g.values():
        assert 0 <= graha.nakshatra_index <= 26
        assert 1 <= graha.pada <= 4
        assert graha.nakshatra_lord in {
            "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"
        }


def test_sun_is_never_combust():
    g = compute_grahas(JD, "krishnamurti", node_type="mean")
    assert g["Sun"].combust is False
