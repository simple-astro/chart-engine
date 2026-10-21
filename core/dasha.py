"""Vimsottari dasha: mahadasha -> antardasha -> pratyantardasha tree.

Derived from the Moon's nakshatra. The first mahadasha's true start precedes
birth by the elapsed portion of the birth nakshatra; periods chain forward from
there for a full 120-year cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core import constants as C

DAYS_PER_YEAR = 365.25
# Days in a dasha year (Settings): the solar year, or the 360-day Savana year some astrologers use.
YEAR_DAYS = {"solar": 365.25, "savana": 360.0}


def year_days(chart: dict) -> float:
    """The dasha-year length a chart was cast with (charts without the setting use the solar year)."""
    return YEAR_DAYS.get((chart.get("meta") or chart).get("dasha_year", "solar"), DAYS_PER_YEAR)


@dataclass
class DashaPeriod:
    lord: str
    level: int            # 1 mahadasha, 2 antardasha, 3 pratyantardasha
    start: datetime
    end: datetime
    children: list["DashaPeriod"] = field(default_factory=list)


def _vimsottari_from(start_lord: str):
    order = C.VIMSOTTARI_ORDER
    idx = order.index(start_lord)
    for i in range(len(order)):
        lord = order[(idx + i) % len(order)]
        yield lord, C.VIMSOTTARI_YEARS[lord]


def dasha_balance(moon_longitude: float) -> tuple[str, float, float]:
    """Return (starting mahadasha lord, elapsed years, balance years)."""
    moon_longitude = moon_longitude % 360.0
    nak_index = int(moon_longitude // C.NAKSHATRA_ARC)
    lord = C.NAKSHATRA_LORDS[nak_index]
    offset = moon_longitude - nak_index * C.NAKSHATRA_ARC
    fraction_elapsed = offset / C.NAKSHATRA_ARC
    lord_years = C.VIMSOTTARI_YEARS[lord]
    elapsed = fraction_elapsed * lord_years
    return lord, elapsed, lord_years - elapsed


def _years_to_delta(years: float, days: float = DAYS_PER_YEAR) -> timedelta:
    return timedelta(days=years * days)


def _build_subtree(lord: str, period_years: float, start: datetime, level: int,
                   max_level: int, days: float = DAYS_PER_YEAR) -> DashaPeriod:
    node = DashaPeriod(lord=lord, level=level, start=start,
                       end=start + _years_to_delta(period_years, days))
    if level < max_level:
        cursor = start
        for sub_lord, sub_years in _vimsottari_from(lord):
            sub_period_years = period_years * sub_years / C.VIMSOTTARI_TOTAL_YEARS
            child = _build_subtree(sub_lord, sub_period_years, cursor, level + 1, max_level, days)
            node.children.append(child)
            cursor = child.end
    return node


def vimshottari_tree(moon_longitude: float, birth_dt: datetime,
                     max_level: int = 3, days_per_year: float = DAYS_PER_YEAR) -> list[DashaPeriod]:
    """Full Vimsottari tree to ``max_level`` for one 120-year cycle.

    The first mahadasha's true start = birth - elapsed portion of the nakshatra.
    """
    lord, elapsed, _balance = dasha_balance(moon_longitude)
    md_true_start = birth_dt - _years_to_delta(elapsed, days_per_year)

    tree: list[DashaPeriod] = []
    cursor = md_true_start
    for md_lord, md_years in _vimsottari_from(lord):
        md = _build_subtree(md_lord, md_years, cursor, level=1, max_level=max_level, days=days_per_year)
        tree.append(md)
        cursor = md.end
    return tree
