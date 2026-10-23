"""The 144 house-lord readings (core/lord_placements.py): complete, short, and free of fear words."""
import re

from core import lord_placements as LP

FEAR = re.compile(r"\b(death|die|dies|dying|fatal|short life|longevity|widow\w*|divorce\w*|curse\w*|doom\w*|disaster\w*)\b", re.I)


def test_every_placement_is_written():
    assert set(LP.PLACEMENTS) == {(a, b) for a in range(1, 13) for b in range(1, 13)}
    for key, r in LP.PLACEMENTS.items():
        assert 100 <= len(r["text"]) <= 260, key   # two or three sentences: enough for people learning
        assert len(r["life"]) == 3 and all(10 <= len(x) <= 120 for x in r["life"]), key


def test_no_fear_words():
    for key, r in LP.PLACEMENTS.items():
        assert not FEAR.search(" ".join([r["text"], *r["life"]])), key


def test_for_a_chart(tmp_path, monkeypatch):
    """The owner's chart (Sagittarius lagna, KP): Jupiter rules 1 and 4 from the 5th, Saturn 2 and 3 from the 12th,
    the Sun at home in the 9th; graded and timed from the chart itself."""
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    req = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884,
           "tz_name": "Asia/Kolkata", "ayanamsha": "krishnamurti"}
    chart = TestClient(app).post("/chart", json=req).json()
    r = LP.for_chart(chart, datetime(2026, 10, 23, tzinfo=timezone.utc))
    by = {c["house"]: c for c in r["cards"]}
    assert (by[1]["lord"], by[1]["sits_in"], by[1]["tag"]) == ("Jupiter", 5, "Strong")
    assert (by[2]["lord"], by[2]["sits_in"], by[2]["tag"]) == ("Saturn", 12, "Needs care")
    assert "Aspects its own 2nd house (protects it)" in by[2]["why"]
    assert by[9]["tag"] == "Strong" and "In its own house" in by[9]["why"]
    assert "Debilitated, cancelled (Neecha Bhanga)" in by[8]["why"] and "Sarala Vipareeta Raja yoga" in by[8]["why"]
    assert by[6]["when"] == "Running now: Venus Mahadasha → Jun 2030"
    assert any(h["t"].startswith("Dharma–Karmadhipati") for h in r["highlights"])
    api = TestClient(app).post("/house-lords", json=req)
    assert api.status_code == 200 and len(api.json()["cards"]) == 12


def test_the_principle():
    p = LP.principle(2, 12)
    assert "2nd lord rules wealth" in p and "the 12th is the 11th" in p
    assert "own house" in LP.principle(9, 9)
    assert "Sarala Vipareeta" in LP.principle(8, 12) and "Harsha" in LP.principle(6, 8) and "Vimala" in LP.principle(12, 6)
    assert "Raja yoga" in LP.principle(4, 5) and "Raja yoga" in LP.principle(5, 10)
    r = LP.reading(1, 5)
    assert r["text"].startswith("Your path runs through learning") and r["principle"].startswith("The 1st lord")
