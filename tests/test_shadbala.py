"""Shadbala against the owner's desktop-software printouts (Deepak Saluja; Sukhdeep, cast there for 14:20).
Known, deliberate differences (core/shadbala.py docstring) are left out: the planetary-war share (the printout adds it
to both planets); Sukhdeep's Jupiter Cheshta
(the printout's (mean + true)/2 is thrown 180° across 0° Aries); his Moon's Saptavarga (D12 boundary, 17°30′)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from core import shadbala as SB

P = SB.P
IST = ZoneInfo("Asia/Kolkata")
D = SB.compute(datetime(1978, 3, 11, 3, 10, tzinfo=IST), 29.69197, 76.98448)
S = SB.compute(datetime(1987, 9, 1, 14, 20, tzinfo=IST), 30.73629, 76.7884)


def col(r, fn):
    return [fn(r["planets"][p]) for p in P]


def close(got, want, tol=0.06, skip=()):
    for i, (g, w) in enumerate(zip(got, want)):
        if i not in skip:
            assert abs(g - w) <= tol, (i, round(g, 2), w)


def test_sthana_and_dig():
    close(col(D, lambda x: x["sthana"]["uchcha"]), [45.50, 45.41, 9.59, 2.57, 49.40, 53.68, 33.97])
    close(col(S, lambda x: x["sthana"]["uchcha"]), [18.40, 4.83, 4.83, 53.64, 30.29, 13.24, 49.64])
    close(col(D, lambda x: x["sthana"]["saptavarga"]), [84.38, 105.00, 90.00, 106.88, 67.50, 84.38, 24.38])
    close(col(S, lambda x: x["sthana"]["saptavarga"]), [135.00, 86.25, 63.75, 75.00, 31.88, 50.63, 101.25], skip={1})
    close(col(D, lambda x: x["sthana"]["total"]), [159.87, 225.41, 189.59, 169.44, 221.90, 228.06, 103.35])
    close(col(D, lambda x: x["dig"]), [14.11, 53.47, 26.80, 34.78, 6.15, 49.74, 46.57])
    close(col(S, lambda x: x["dig"]), [49.43, 20.33, 48.65, 28.21, 18.48, 9.74, 3.41])


@pytest.mark.parametrize("part,dref,sref", [
    ("nathonnatha", [13.97, 46.03, 46.03, 60, 13.97, 13.97, 46.03], [50.23, 9.77, 9.77, 60, 50.23, 50.23, 9.77]),
    ("paksha", [52.42, 104.84, 52.42, 7.58, 7.58, 7.58, 52.42], [29.10, 58.20, 29.10, 30.90, 30.90, 30.90, 29.10]),
    ("abda", [15, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 15, 0, 0]),
    ("masa", [0, 0, 0, 30, 0, 0, 0], [0, 0, 30, 0, 0, 0, 0]),
    ("ayana", [49.90, 23.61, 57.31, 30.38, 59.76, 30.76, 13.43], [81.34, 58.10, 41.77, 35.27, 44.39, 39.49, 58.85]),
])
def test_kala_parts(part, dref, sref):
    close(col(D, lambda x: x["kala"][part]), dref)
    close(col(S, lambda x: x["kala"][part]), sref)


def test_day_birth_matches_every_kala_part():
    close(col(S, lambda x: x["kala"]["total"]), [280.67, 126.07, 155.64, 126.17, 200.53, 120.62, 97.72])


@pytest.mark.parametrize("part,ref", [("tribhaga", [0, 60, 0, 0, 60, 0, 0]), ("vara", [0, 0, 0, 0, 0, 0, 45]),
                                      ("hora", [0, 60, 0, 0, 0, 0, 0])])
def test_pre_sunrise_birth_keeps_the_calendar_day_like_the_printout(part, ref):
    close(col(D, lambda x: x["kala"][part]), ref)


def test_pre_sunrise_kala_and_totals_match_but_for_the_war_share():
    kala = col(D, lambda x: x["kala"]["total"] - x["kala"]["yuddha"])
    close(kala, [131.29, 294.49, 155.77, 128.17 - 0.21, 141.30, 52.52 - 0.21, 156.89])
    close(col(D, lambda x: x["total"]), [353.84, 612.46, 455.58, 366.89, 454.91, 368.19, 374.85], tol=2.5)


def test_cheshta_drik_and_war():
    close(col(D, lambda x: x["cheshta"]), [0, 0, 45.99, 22.63, 34.20, 8.77, 51.71], tol=2.3)
    close(col(S, lambda x: x["cheshta"]), [0, 0, 1.48, 6.61, 15.68, 1.87, 32.29], tol=2.3, skip={4})
    close(col(D, lambda x: x["drik"]), [-11.43, -12.34, 20.29, -13.83, 17.08, -13.74, 7.76])
    close(col(S, lambda x: x["drik"]), [12.32, 4.88, 12.90, -1.71, -2.65, 11.70, 5.78])
    assert [w["planets"] for w in D["wars"]] == [["Mercury", "Venus"]] and not S["wars"]
    w = D["wars"][0]
    assert D["planets"][w["winner"]]["kala"]["yuddha"] == -D["planets"][w["loser"]]["kala"]["yuddha"] > 0


def test_ranks_follow_the_printouts():
    assert col(D, lambda x: x["rank"]) == [7, 1, 2, 6, 3, 5, 4]
    assert col(S, lambda x: x["rank"]) == [1, 5, 4, 3, 2, 7, 6]


def test_bhava_bala():
    assert [b["dig"] for b in S["bhavas"]] == [60, 20, 40, 60, 10, 20, 0, 20, 50, 30, 40, 10]
    assert [b["dig"] for i, b in enumerate(D["bhavas"]) if i != 1] == [30, 50, 0, 10, 20, 0, 20, 20, 30, 20, 10]
    close([b["drishti"] for b in S["bhavas"]], [62.3, 33.8, 5.0, 35.1, 25.3, 22.6, 23.5, 44.3, 54.0, 8.9, 61.1, 59.9], tol=0.1)
    close([b["drishti"] for b in D["bhavas"]], [49.7, 8.7, 26.9, -9.9, -2.5, 26.5, 50.2, 29.7, 96.9, 82.1, 55.5, 67.7], tol=0.4)
    assert [b["lord"] for b in D["bhavas"]][:4] == ["Jupiter", "Saturn", "Jupiter", "Mars"]
    assert sorted(b["rank"] for b in S["bhavas"]) == list(range(1, 13))


def test_endpoint(tmp_path, monkeypatch):
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    r = TestClient(app).post("/shadbala", json={"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.73629,
                                                "lon": 76.7884, "tz_name": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert abs(d["planets"]["Sun"]["total"] - 600.82) < 1 and len(d["bhavas"]) == 12
