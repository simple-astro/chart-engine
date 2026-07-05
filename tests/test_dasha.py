"""Vimsottari dasha tree tests."""
from datetime import datetime, timezone

from core.constants import NAKSHATRA_ARC, VIMSOTTARI_YEARS, VIMSOTTARI_ORDER
from core.dasha import vimshottari_tree, dasha_balance

BIRTH = datetime(1990, 8, 15, 6, 30, tzinfo=timezone.utc)


def test_balance_is_full_period_at_nakshatra_start():
    # Moon at 0.0 = start of Ashwini (Ketu). Nothing elapsed -> full 7-year balance.
    lord, elapsed, balance = dasha_balance(0.0)
    assert lord == "Ketu"
    assert abs(elapsed) < 1e-9
    assert abs(balance - VIMSOTTARI_YEARS["Ketu"]) < 1e-9


def test_balance_is_half_at_nakshatra_midpoint():
    lord, elapsed, balance = dasha_balance(NAKSHATRA_ARC / 2)
    assert lord == "Ketu"
    assert abs(balance - VIMSOTTARI_YEARS["Ketu"] / 2) < 1e-9


def test_first_mahadasha_lord_matches_moon_nakshatra():
    tree = vimshottari_tree(0.0, BIRTH)
    assert tree[0].lord == "Ketu"
    assert tree[0].level == 1


def test_full_cycle_of_mahadashas_sums_to_120_years():
    tree = vimshottari_tree(0.0, BIRTH)
    total_days = sum((p.end - p.start).total_seconds() for p in tree) / 86400.0
    assert abs(total_days - 120 * 365.25) < 1e-3
    assert len(tree) == 9


def test_antardashas_start_with_mahadasha_lord_and_sum_to_it():
    tree = vimshottari_tree(0.0, BIRTH)
    md = tree[0]
    assert md.children[0].lord == md.lord
    ad_days = sum((c.end - c.start).total_seconds() for c in md.children) / 86400.0
    md_days = (md.end - md.start).total_seconds() / 86400.0
    assert abs(ad_days - md_days) < 1e-6
    # antardasha lords follow Vimsottari order starting at the MD lord
    order_from_ketu = VIMSOTTARI_ORDER  # MD lord Ketu is first
    assert [c.lord for c in md.children] == order_from_ketu


def test_pratyantardashas_present_and_sum_to_antardasha():
    tree = vimshottari_tree(0.0, BIRTH)
    ad = tree[0].children[0]
    assert ad.children[0].lord == ad.lord
    pd_days = sum((c.end - c.start).total_seconds() for c in ad.children) / 86400.0
    ad_days = (ad.end - ad.start).total_seconds() / 86400.0
    assert abs(pd_days - ad_days) < 1e-6
    assert ad.level == 2 and ad.children[0].level == 3


def test_periods_chain_without_gaps():
    tree = vimshottari_tree(0.0, BIRTH)
    for a, b in zip(tree, tree[1:]):
        assert a.end == b.start
    md = tree[0]
    for a, b in zip(md.children, md.children[1:]):
        assert a.end == b.start


def test_first_mahadasha_true_start_precedes_birth_when_balance_partial():
    # Half-elapsed Ketu: true MD start is 3.5 years before birth.
    tree = vimshottari_tree(NAKSHATRA_ARC / 2, BIRTH)
    assert tree[0].start < BIRTH
