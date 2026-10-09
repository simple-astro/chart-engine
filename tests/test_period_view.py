"""What the running period lords promise across life matters."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import period_view as pv, storage, transit_view
from app.main import app
from core import kp_predict as K

A = {"name": "A", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    return TestClient(app)


def test_period_lords_are_judged_like_the_timing_engine(client):
    p = storage.get(client.post("/profiles", json=A).json()["id"])
    day = date(2026, 1, 1)
    ov = transit_view.overlay(p, day)
    r = pv.periods(p["chart"], day, ov["dasha"], ov["planets"])
    lords = [d["lord"] for d in ov["dasha"]]
    assert [x["lord"] for x in r["lords"]] == list(dict.fromkeys(lords))
    for m in r["matrix"]:
        for lv, cell in m["cells"].items():
            lord = next(d["lord"] for d in ov["dasha"] if d["level"] == lv)
            assert cell["verdict"] == K.lord_verdict(p["chart"], m["topic"], lord)["verdict"]
    for x in r["lords"]:
        lv = x["level"]
        for t in pv.TOPICS:
            v = next(m for m in r["matrix"] if m["topic"] == t)["cells"][lv]["verdict"]
            if t == "health" and x["care"] == "mixed":
                assert pv.SHORT[t] not in x["strong"] + x["leans"]
                continue
            assert (pv.SHORT[t] in x["strong"]) == (v == "supports" and K.TOPICS[t][6] == "event")
            assert (pv.SHORT[t] in x["leans"]) == (v == "leans good" and K.TOPICS[t][6] == "event")
        assert x["summary"].startswith(f"Your {x['lord']} {x['title']}")


def test_summary_wording():
    s = pv._lord_summary("Antardasha and Pratyantar", "Mercury", ["Abroad"], ["Money", "Property"], ["Children"], True)
    assert s == ("Your Mercury Antardasha and Pratyantar strongly support abroad; lean towards money and property; "
                 "work against children; ask for care with health.")
    assert pv._lord_summary("Mahadasha", "Venus", [], [], [], False) == "Your Venus Mahadasha is neutral for most matters."
    assert pv._lord_summary("Antardasha", "Mars", [], [], [], "mixed") == \
        "Your Mars Antardasha gives mixed signals for health — keep a steady routine."


def test_retrograde_transit_of_a_period_lord_is_not_read(monkeypatch):
    chart = {"grahas": {"Venus": {"house": 9, "sign": "Leo", "retrograde": False}}}
    monkeypatch.setattr(pv.K, "lord_verdict", lambda c, t, p: {"verdict": "mixed", "star_lord": "Venus", "sub_lord": "Moon",
                                                               "levels": {"planet": {"houses": [9]}}})
    monkeypatch.setattr(pv.K, "predict", lambda *a, **k: {"windows": []})
    monkeypatch.setattr(pv.K, "promise", lambda *a, **k: {"verdict": "promised"})
    dasha = [{"level": "maha", "lord": "Venus", "start": "2010-01-01", "end": "2030-01-01"}]
    planets = [{"planet": "Venus", "h_bhava": 10, "sign": "Libra", "star_lord": "Rahu", "sub_lord": "Mercury", "retrograde": True}]
    t = pv.periods(chart, date(2026, 10, 9), dasha, planets)["lords"][0]["transit"]
    assert t["retrograde"] and t["supports"] == [] and t["promised_too"] == []


def test_endpoint_includes_periods(client):
    pid = client.post("/profiles", json=A).json()["id"]
    r = client.get(f"/profiles/{pid}/transit/events?date=2026-01-01").json()
    assert r["periods"]["lords"] and len(r["periods"]["matrix"]) == len(pv.TOPICS)
