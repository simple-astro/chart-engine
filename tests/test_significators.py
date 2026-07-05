"""KP significator + cuspal-house-placement tests."""
from datetime import datetime, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.kp import planet_house, houses_owned, planet_significators, house_significators

JD = julian_day(datetime(1990, 8, 15, 6, 30, tzinfo=timezone.utc))
LAT, LON = 28.6139, 77.2090
G = compute_grahas(JD, "krishnamurti", node_type="mean")
H = compute_houses(JD, LAT, LON, "krishnamurti")


def test_planet_house_in_valid_range():
    for graha in G.values():
        h = planet_house(graha.longitude, H)
        assert 1 <= h <= 12


def test_planet_at_ascendant_is_house_one():
    assert planet_house(H.ascendant, H) == 1


def test_owned_houses_have_matching_sign_lord():
    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        owned = houses_owned(planet, H)
        for house_num in owned:
            assert H.cusps[house_num - 1].sign_lord == planet


def test_significators_reference_valid_houses():
    sig = planet_significators(G, H)
    assert set(sig) == set(G)  # all nine grahas
    for planet, data in sig.items():
        assert all(1 <= h <= 12 for h in data["houses"])
        # the flattened set is the union of the four levels
        union = set(data["occupied_by_star_lord"]) | set(data["owned_by_star_lord"]) \
            | set(data["occupied"]) | set(data["owned"])
        assert set(data["houses"]) == union


def test_house_significators_is_inverse_of_planet_significators():
    psig = planet_significators(G, H)
    hsig = house_significators(G, H)
    assert set(hsig) == set(range(1, 13))
    for planet, data in psig.items():
        for house_num in data["houses"]:
            assert planet in hsig[house_num]
    for house_num, planets in hsig.items():
        for planet in planets:
            assert house_num in psig[planet]["houses"]
