"""Transit significators and the Promise -> Dasha -> Trigger ladder."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import storage, transit_events as te, transit_view
from app.main import app

A = {"name": "A", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    return TestClient(app)


def test_transit_verdict_follows_the_sub_lord():
    good, bad = {2, 7, 11}, {1, 6, 10}
    assert te.transit_verdict({7}, {2, 11}, good, bad) == "supports"
    assert te.transit_verdict({7}, {1, 6}, good, bad) == "against"        # the sub lord negates
    assert te.transit_verdict({3}, {2, 6, 10}, good, bad) == "mixed"      # more against than for in the sub
    assert te.transit_verdict({3}, {4, 5}, good, bad) == "neutral"


def test_ladder_and_strict_trigger(client):
    pid = client.post("/profiles", json=A).json()["id"]
    p = storage.get(pid)
    day = date(2026, 1, 1)
    ov = transit_view.overlay(p, day)
    e = te.events(p, day, ov)
    assert len(e["rows"]) == 9 and {r["planet"] for r in e["rows"]} == {x["planet"] for x in ov["planets"]}
    assert all(set(r["topics"]) == set(te.TOPICS) for r in e["rows"])
    dl = {x["lord"] for x in ov["dasha"]}
    for x in e["ladder"]:
        if x["status"] in ("strong", "open"):  # the status rests on promise + dasha only
            assert x["promise"]["ok"] and x["dasha"]["ok"]
        for t in x["trigger"]["planets"]:  # every trigger: a slow planet in a sign, star and sub of dasha lords
            r = next(r for r in e["rows"] if r["planet"] == t["planet"])
            assert r["planet"] in te.SLOW and {r["sign_lord"], r["star_lord"], r["sub_lord"]} <= dl
        if x["status"] == "not_now":
            assert not x["dasha"]["ok"]
    hinted = [x for x in e["ladder"] if x["trigger"]["planets"]]
    assert "property" in [x["topic"] for x in hinted] and len(hinted) < len(te.TOPICS)
    for x in hinted:  # the hint is specific: the transit's sub lord must support that very matter
        for t in x["trigger"]["planets"]:
            assert next(r for r in e["rows"] if r["planet"] == t["planet"])["topics"][x["topic"]] == "supports"
    order = [x["status"] for x in e["ladder"]]
    assert order == sorted(order, key=["strong", "open", "not_now", "not_promised"].index)


def test_retrograde_or_stationary_jupiter_and_saturn_carry_no_trigger():
    row = lambda **k: {"planet": "Jupiter", "retrograde": False, "speed": 0.08, **k}
    assert not te.inert(row()) and te.inert(row(retrograde=True)) and te.inert(row(speed=0.005))
    assert not te.inert({"planet": "Rahu", "retrograde": False, "speed": -0.05})  # nodes are exempt
    table = [{"planet": "Saturn", "sign_lord": "Venus", "star_lord": "Moon", "sub_lord": "Venus",
              "topics": {"marriage": "supports"}, "retrograde": True, "speed": -0.02, "inert": True}]
    assert te.strict_triggers(table, {"Venus", "Moon"}, "marriage") == []
    assert te.strict_triggers(table, {"Venus", "Moon"}, "marriage", skip_inert=False)


def test_nature_notes(client):
    pid = client.post("/profiles", json=A).json()["id"]
    c = storage.get(pid)["chart"]
    win = {"maha": "Venus", "antar": "Mercury", "praty": "Sun"}
    hs = set().union(*(te.K.fourfold(c, p) for p in win.values()))
    notes = te.nature(c, "marriage", win)
    assert any("love marriage" in n for n in notes) == (5 in hs)
    assert any("finalising" in n for n in notes) == (11 not in hs)
    assert te.nature(c, "career", win)[0] == "The Mercury period points to work in business, communication, accounts or IT."


def test_endpoint(client):
    pid = client.post("/profiles", json=A).json()["id"]
    r = client.get(f"/profiles/{pid}/transit/events?date=2026-01-01")
    assert r.status_code == 200 and r.json()["ladder"]
    assert client.get(f"/profiles/{pid}/transit/events?date=2026-13-01").status_code == 422
    assert client.get("/profiles/9999/transit/events").status_code == 404
