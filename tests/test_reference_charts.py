"""Golden-master regression: full chart output for fixed reference births.

The snapshot is generated once from the engine's own output (bootstrap) and then
frozen. Any future change in computed values fails here, forcing a conscious
review. The product owner independently verifies one chart against Horosoft/KP
software and those numbers are then trusted (see design doc §5).
"""
import json
from datetime import date, time
from pathlib import Path

import pytest

from core.chart import BirthData, chart_to_json, compute_natal_chart

GOLDEN_DIR = Path(__file__).parent / "golden"

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

    expected = golden_path.read_text(encoding="utf-8")
    assert produced == expected, (
        f"chart output drifted from {golden_path.name}. If intentional, delete the "
        f"golden file and re-run to regenerate."
    )
    # sanity: the snapshot is real, complete JSON
    parsed = json.loads(expected)
    assert len(parsed["grahas"]) == 9 and len(parsed["vargas"]) == 16
