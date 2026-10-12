"""Yogini Dasha: eight periods totalling 36 years, starting from the birth nakshatra.

The first Yogini is (birth nakshatra number + 3), counted 1..8 round the cycle Mangala, Pingala, Dhanya, Bhramari,
Bhadrika, Ulka, Siddha, Sankata (1..8 years). The birth balance is the part of the Moon's nakshatra still to run.
Sub-periods follow the same order from the main period's Yogini, each lasting main years x sub years / 36.
Years are 365.25 days, as in the Vimshottari engine (core.dasha).

Shown as a second opinion beside Vimshottari, with the traditional names and gentle descriptions. It does not
change any verdict until a backtest supports it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

NAK_SPAN = 360.0 / 27.0
DAYS_PER_YEAR = 365.25
TOTAL = 36
YOGINIS = [  # name, planet, years, gentle description, tone
    ("Mangala", "Moon", 1, "Auspicious and gentle — good beginnings, peace of mind and warmth at home.", "good"),
    ("Pingala", "Sun", 2, "Heat and pressure — dealings with authority and pride; look after your health and temper.", "care"),
    ("Dhanya", "Jupiter", 3, "Growth and plenty — wealth, learning and blessings come more easily.", "good"),
    ("Bhramari", "Mars", 4, "On the move — travel, change and restlessness; put the energy into action.", "mixed"),
    ("Bhadrika", "Mercury", 5, "Good relations and gains — friends, trade and studies go well.", "good"),
    ("Ulka", "Saturn", 6, "Hard work and slower results — steady effort pays; avoid shortcuts and rest well.", "care"),
    ("Siddha", "Venus", 7, "Success and comfort — wishes come true; relationships and comforts grow.", "good"),
    ("Sankata", "Rahu", 8, "A testing stretch — unexpected turns; steady habits, care with risks and advice from "
                           "elders carry you through.", "care"),
]


def _jd_to_utc(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def _period(i: int, start: datetime, years: float) -> dict:
    name, planet, _, text, tone = YOGINIS[i]
    end = start + timedelta(days=years * DAYS_PER_YEAR)
    return {"yogini": name, "planet": planet, "start": start.isoformat(), "end": end.isoformat(),
            "years": round(years, 4), "text": text, "tone": tone}


def yogini_dasha(moon_longitude: float, birth_utc: datetime, cycles: int = 3) -> list[dict]:
    """Main periods from birth for ``cycles`` x 36 years, each with its sub-periods."""
    nak = int(moon_longitude // NAK_SPAN)  # 0-based
    first = (nak + 1 + 3 - 1) % 8           # (nakshatra number + 3), 1..8 -> 0..7
    done = (moon_longitude % NAK_SPAN) / NAK_SPAN
    full = YOGINIS[first][2]
    # The first period began before birth: the elapsed part of the nakshatra.
    start = birth_utc - timedelta(days=done * full * DAYS_PER_YEAR)
    out = []
    for k in range(8 * cycles):
        i = (first + k) % 8
        years = YOGINIS[i][2]
        main = _period(i, start, years)
        subs, s = [], start
        for j in range(8):
            si = (i + j) % 8
            sy = years * YOGINIS[si][2] / TOTAL
            subs.append(_period(si, s, sy))
            s = s + timedelta(days=sy * DAYS_PER_YEAR)
        main["sub"] = subs
        out.append(main)
        start = start + timedelta(days=years * DAYS_PER_YEAR)
    return out


def summary(chart: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    birth = _jd_to_utc(chart["meta"]["julian_day"])
    periods = yogini_dasha(chart["grahas"]["Moon"]["longitude"], birth)
    iso = now.isoformat()
    cur = next((p for p in periods if p["start"] <= iso < p["end"]), None)
    sub = cur and next((s for s in cur["sub"] if s["start"] <= iso < s["end"]), None)
    nxt = cur and next((p for p in periods if p["start"] >= cur["end"]), None)
    # From the main period before the current one to a few ahead: enough for a timeline without the whole life.
    i = periods.index(cur) if cur else 0
    return {"current": cur and {k: v for k, v in cur.items() if k != "sub"},
            "sub": sub, "next": nxt and {k: v for k, v in nxt.items() if k != "sub"},
            "timeline": [{k: v for k, v in p.items() if k != "sub"} for p in periods[max(0, i - 1): i + 6]],
            "current_subs": cur["sub"] if cur else []}
