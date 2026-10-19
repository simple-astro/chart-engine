"""Backtest: do the book's dated events fall near a Paryaya crossing (transiting Jupiter or Saturn on the exact
degree of a natal planet or the Lagna) more often than an ordinary day does?

For each dated event (tests/test_book_backtest.py), an event "hits" if a crossing falls within +/- WINDOW days.
The base rate is the share of all days in each native's life (age 16 to 60) that are within WINDOW days of a
crossing. Run: .venv/bin/python scripts/backtest_paryaya.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core import paryaya  # noqa: E402
from tests.test_book_backtest import EVENTS  # noqa: E402

WINDOW = 30


def near(days: set[date], d: date) -> bool:
    return any(abs((x - d).days) <= WINDOW for x in days)


def main() -> None:
    cl = TestClient(app)
    charts, hits, base = {}, [], []
    for label, dob, tob, (lat, lon), topic, when, dba in EVENTS:
        if when is None:
            continue
        key = (dob, tob, lat, lon)
        if key not in charts:
            c = cl.post("/chart", json={"dob": dob, "tob": tob + ":00", "lat": lat, "lon": lon,
                                        "tz_name": "Asia/Kolkata"}).json()
            b = date.fromisoformat(dob)
            lo, hi = b + timedelta(days=16 * 365), b + timedelta(days=60 * 365)
            cross = {date.fromisoformat(x["date"]) for x in paryaya.crossings(c, lo, hi)}
            days = [lo + timedelta(days=i) for i in range(0, (hi - lo).days, 7)]
            base.append(sum(near(cross, d) for d in days) / len(days))
            charts[key] = cross
        hit = near(charts[key], date.fromisoformat(when))
        hits.append(hit)
        print(f"{'HIT ' if hit else 'miss'} {label}")
    rate, br = sum(hits) / len(hits), sum(base) / len(base)
    print(f"\n{sum(hits)}/{len(hits)} events within {WINDOW} days of a crossing ({rate:.0%}); "
          f"base rate {br:.0%}; lift x{rate / br:.2f}")


if __name__ == "__main__":
    main()
