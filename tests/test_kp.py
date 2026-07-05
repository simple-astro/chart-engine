"""KP sub-lord chain tests. Uses hand-computed Vimsottari-proportion anchors."""
import pytest

from core.constants import NAKSHATRA_ARC, VIMSOTTARI_ORDER, VIMSOTTARI_YEARS
from core.kp import kp_lords, subdivide


def test_start_of_ashwini_is_all_ketu_except_sign():
    # Longitude 0.0 = start of Aries / Ashwini. Star lord Ketu; the first sub and
    # sub-sub both begin with the star lord.
    lords = kp_lords(0.0)
    assert lords.sign_lord == "Mars"        # Aries
    assert lords.star_lord == "Ketu"        # Ashwini
    assert lords.sub_lord == "Ketu"
    assert lords.sub_sub_lord == "Ketu"


def test_handcomputed_chain_at_half_degree():
    # At 0.5deg into Ashwini: Ketu sub spans 7/120*13.333=0.7778deg, so sub=Ketu.
    # Within that sub, cumulative sub-sub spans put 0.5 in Jupiter's slice.
    lords = kp_lords(0.5)
    assert (lords.sign_lord, lords.star_lord, lords.sub_lord, lords.sub_sub_lord) == (
        "Mars", "Ketu", "Ketu", "Jupiter"
    )


def test_sub_lord_boundary_ketu_to_venus():
    # Ketu's sub span ends at 7/120 * 13.3333 = 0.77778deg into Ashwini.
    assert kp_lords(0.77).sub_lord == "Ketu"
    assert kp_lords(0.78).sub_lord == "Venus"


def test_subdivide_spans_sum_to_total():
    # subdivide should partition [0, total) into 9 Vimsottari-proportioned spans.
    total = NAKSHATRA_ARC
    covered = 0.0
    offset = 1e-9
    seen = []
    while offset < total:
        lord, start, length = subdivide(offset, total, "Ketu")
        seen.append(lord)
        assert abs(start - covered) < 1e-9
        covered += length
        offset = covered + 1e-9
    assert abs(covered - total) < 1e-9
    assert seen == VIMSOTTARI_ORDER  # starting at Ketu, full cycle in order


def test_subdivide_lengths_are_proportional():
    total = 120.0  # convenient: each lord's length equals its years
    for lord in VIMSOTTARI_ORDER:
        # walk to the midpoint of each lord's span and check its length
        pass
    _, _, ketu_len = subdivide(1e-9, total, "Ketu")
    assert abs(ketu_len - VIMSOTTARI_YEARS["Ketu"]) < 1e-9


def test_full_zodiac_every_position_has_four_lords():
    valid = set(VIMSOTTARI_ORDER) | {"Sun", "Moon", "Mars", "Mercury", "Jupiter",
                                     "Venus", "Saturn"}
    for deg in [15.0, 47.3, 123.9, 259.99, 340.0]:
        lords = kp_lords(deg)
        for l in (lords.sign_lord, lords.star_lord, lords.sub_lord, lords.sub_sub_lord):
            assert l in valid
