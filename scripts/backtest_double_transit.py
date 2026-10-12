"""Backtest the "double transit": an event the chart promises happens when transiting Jupiter AND Saturn both
aspect or occupy the event's house. Tested on the book's dated events (tests/test_book_backtest.py) against the
base rate: how often the same condition holds on a random day of the native's adult life (18 to 60).

Jupiter touches a house from its own sign by occupation or its 5th / 7th / 9th aspect; Saturn by occupation or its
3rd / 7th / 10th aspect. The house is read three ways: whole-sign from the Lagna, from the Moon, and the sign on the
KP (Placidus) cusp.

    .venv/bin/python scripts/backtest_double_transit.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core import kp_predict as K  # noqa: E402
from core.transits import transit_positions  # noqa: E402
from tests.test_book_backtest import EVENTS  # noqa: E402

JUP, SAT = {1, 5, 7, 9}, {1, 3, 7, 10}
_cache: dict[date, tuple[int, int]] = {}


def js_signs(d: date) -> tuple[int, int]:
    if d not in _cache:
        tr = transit_positions(datetime(d.year, d.month, d.day, 6, tzinfo=timezone.utc), "krishnamurti")
        _cache[d] = (tr["Jupiter"].sign_index, tr["Saturn"].sign_index)
    return _cache[d]


def touches(target: int, d: date) -> bool:
    j, s = js_signs(d)
    return (target - j) % 12 + 1 in JUP and (target - s) % 12 + 1 in SAT


def main() -> None:
    c = TestClient(app)
    rows = {"lagna": [0, 0.0], "moon": [0, 0.0], "cusp": [0, 0.0]}
    n = 0
    for label, dob, tob, (lat, lon), topic, when, _dba in EVENTS:
        if not when:
            continue
        n += 1
        ch = c.post("/chart", json={"dob": dob, "tob": tob + ":00", "lat": lat, "lon": lon,
                                    "tz_name": "Asia/Kolkata"}).json()
        h = K.TOPICS[topic][1]
        targets = {"lagna": (ch["lagna"]["sign_index"] + h - 1) % 12,
                   "moon": (ch["grahas"]["Moon"]["sign_index"] + h - 1) % 12,
                   "cusp": ch["houses"][h - 1]["sign_index"]}
        d0 = date.fromisoformat(dob)
        days = [d0 + timedelta(days=round(18 * 365.25)) + timedelta(days=7 * i) for i in range(round(42 * 52.18))]
        ev = date.fromisoformat(when)
        line = []
        for k, t in targets.items():
            hit = touches(t, ev)
            base = sum(touches(t, d) for d in days) / len(days)
            rows[k][0] += hit
            rows[k][1] += base
            line.append(f"{k}:{'HIT' if hit else '-'}({base:.0%})")
        print(f"{label:28} H{h:<2} {' '.join(line)}")
    print(f"\n{n} dated events")
    for k, (hits, exp) in rows.items():
        print(f"  from {k:5}: {hits}/{n} hit, {exp:.1f} expected by chance  (x{hits / exp:.2f})")


if __name__ == "__main__":
    main()
