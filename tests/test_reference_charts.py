"""Golden-master regression: full chart output for fixed reference births.

The snapshot is generated once from the engine's own output (bootstrap) and then
frozen. Any future change in computed values fails here, forcing a conscious
review. The product owner independently verifies one chart against Horosoft/KP
software and those numbers are then trusted (see design doc §5).
"""
import json
import math
from datetime import date, datetime, time
from pathlib import Path

import pytest

from core.chart import BirthData, chart_to_json, compute_natal_chart

GOLDEN_DIR = Path(__file__).parent / "golden"


def _assert_close(produced, expected, path="$"):
    """Deep-compare parsed JSON with a float tolerance, so the snapshot is stable
    across platforms: the Moshier ephemeris' last-digit float output differs
    between arch/OS (e.g. arm64 macOS vs x64 Linux), which byte-equality would
    flag as spurious drift. Numbers must match within tolerance; everything else
    (strings, bools, structure) must match exactly — so a real logic change still
    fails here."""
    # bool is a subclass of int — check it before the numeric branch
    if isinstance(expected, bool) or isinstance(produced, bool):
        assert produced == expected, f"bool mismatch at {path}: {produced!r} != {expected!r}"
    elif isinstance(expected, (int, float)) and isinstance(produced, (int, float)):
        assert math.isclose(produced, expected, rel_tol=1e-7, abs_tol=1e-5), \
            f"number drift at {path}: {produced} != {expected}"
    elif isinstance(expected, dict):
        assert isinstance(produced, dict) and produced.keys() == expected.keys(), \
            f"dict keys differ at {path}: {set(produced) ^ set(expected)}"
        for k in expected:
            _assert_close(produced[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(produced, list) and len(produced) == len(expected), \
            f"list length differs at {path}: {len(produced)} != {len(expected)}"
        for i, (p, e) in enumerate(zip(produced, expected)):
            _assert_close(p, e, f"{path}[{i}]")
    else:
        # ISO datetimes (e.g. dasha boundaries) carry platform-sensitive sub-second
        # noise from the float ephemeris positions; compare within a small tolerance.
        de, dp = _iso_datetime(expected), _iso_datetime(produced)
        if de is not None and dp is not None:
            assert abs((dp - de).total_seconds()) < 2, \
                f"datetime drift at {path}: {produced} != {expected}"
        else:
            assert produced == expected, f"value mismatch at {path}: {produced!r} != {expected!r}"


def _iso_datetime(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if isinstance(dt, datetime) else None

REFERENCES = {
    "reference_delhi_noon": BirthData(
        name="Reference Delhi Noon",
        dob=date(1990, 8, 15), tob=time(12, 0, 0),
        lat=28.6139, lon=77.2090, tz_name="Asia/Kolkata",
    ),
    "reference_winnipeg_morning": BirthData(
        name="Reference Winnipeg Morning",
        dob=date(1985, 3, 21), tob=time(6, 30, 0),
        lat=49.8951, lon=-97.1384, tz_name="America/Winnipeg",
    ),
}


@pytest.mark.parametrize("key", list(REFERENCES))
def test_reference_chart_matches_golden(key):
    chart = compute_natal_chart(REFERENCES[key])
    produced = chart_to_json(chart)

    golden_path = GOLDEN_DIR / f"{key}.json"
    if not golden_path.exists():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(produced, encoding="utf-8")
        pytest.skip(f"bootstrapped golden snapshot {golden_path.name}; re-run to assert")

    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    _assert_close(json.loads(produced), expected)
    # sanity: the snapshot is real, complete JSON
    assert len(expected["grahas"]) == 9 and len(expected["vargas"]) == 16
