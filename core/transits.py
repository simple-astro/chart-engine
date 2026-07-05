"""Transit (current/arbitrary-datetime) positions.

Thin layer over the graha engine so the backend can request positions at any
instant for transit-event detection (FR-14) and live chat context (FR-7).
"""
from __future__ import annotations

from datetime import datetime

from core.ephemeris import julian_day
from core.grahas import Graha, compute_grahas


def transit_positions(dt_utc: datetime, ayanamsha: str = "krishnamurti",
                      node_type: str = "mean") -> dict[str, Graha]:
    """All nine graha positions at an arbitrary UTC datetime."""
    return compute_grahas(julian_day(dt_utc), ayanamsha, node_type=node_type)
