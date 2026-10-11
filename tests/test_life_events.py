"""Life events: entered by the person, checked against their chart and against chance; private; admin backtest."""
import pytest
from fastapi.testclient import TestClient

from app import storage, synthesis
from app.main import app
from tests.test_admin import _admin, _tester, gated  # noqa: F401  (fixture)

H1 = {"name": "H1", "dob": "1950-06-07", "tob": "22:30:00", "lat": 28.6667, "lon": 77.2167, "tz_name": "Asia/Kolkata"}
BOOK = [("engaged", 1978, 12, 4), ("married", 1979, 6, 29), ("home", 1986, 3, 10), ("home", 1994, 5, 25),
        ("sold", 1994, 5, 13), ("vehicle", 1995, 6, 3), ("vehicle", 1995, 12, 13), ("court_win", 1997, 10, 15)]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("TESTER_ACCESS_CODES", raising=False)
    return TestClient(app)


def test_the_books_events_fit_the_chart_better_than_chance(client):
    pid = client.post("/profiles", json=H1).json()["id"]
    for kind, y, m, d in BOOK:
        r = client.post(f"/profiles/{pid}/events", json={"kind": kind, "year": y, "month": m, "day": d})
        assert r.status_code == 200, r.text
    v = r.json()
    assert [e["date"] for e in v["events"]] == sorted(e["date"] for e in v["events"])  # a life story: oldest first
    married = next(e for e in v["events"] if e["kind"] == "married")
    assert married["label"] == "Got married" and married["check"]["fit"] == "fits" and "marriage" in married["check"]["why"]
    s = v["summary"]
    assert s["events"] == 8 and s["fits"] >= 6 and s["fits"] > s["expected"] + 1.5 and s["verdict"] == "good"
    assert "by chance" in s["text"].lower()


def test_dates_are_checked_and_precision_follows_what_is_known(client):
    pid = client.post("/profiles", json=H1).json()["id"]
    add = lambda **b: client.post(f"/profiles/{pid}/events", json={"kind": "job", **b})
    assert add(year=1949).status_code == 422          # before birth
    assert add(year=2099).status_code == 422          # in the future
    assert add(year=1980, month=2, day=30).status_code == 422
    assert add(year=1980, day=3).status_code == 422   # a day without a month
    assert client.post(f"/profiles/{pid}/events", json={"kind": "lottery", "year": 1980}).status_code == 422
    ev = add(year=1975).json()["events"][0]
    assert ev["precision"] == "year" and ev["check"]["rough"]
    assert add(year=1976, month=4).json()["events"][1]["precision"] == "month"


def test_few_events_dont_claim_anything(client):
    pid = client.post("/profiles", json=H1).json()["id"]
    s = client.post(f"/profiles/{pid}/events", json={"kind": "married", "year": 1979, "month": 6}).json()["summary"]
    assert s["verdict"] is None and "Add a few more" in s["text"]


def test_events_are_private_removable_and_known_to_sukh(gated):
    a, b = _tester(), _tester()
    pid = a.post("/profiles", json=H1).json()["id"]
    v = a.post(f"/profiles/{pid}/events", json={"kind": "married", "year": 1979, "month": 6, "day": 29}).json()
    assert b.get(f"/profiles/{pid}/events").status_code == 404
    assert synthesis.build(storage.get(pid))["life_events"]["entered_by_the_person"] == ["1979-06-29: Got married"]
    eid = v["events"][0]["id"]
    assert b.delete(f"/profiles/{pid}/events/{eid}").status_code == 404
    assert a.delete(f"/profiles/{pid}/events/{eid}").json()["events"] == []
    a.post(f"/profiles/{pid}/events", json={"kind": "child", "year": 1982})
    a.delete(f"/profiles/{pid}")
    assert storage.event_list(pid) == []


def test_admin_sees_fits_against_chance_without_year_only_dates(gated):
    t = _tester()
    pid = t.post("/profiles", json=H1).json()["id"]
    for kind, y, m, d in BOOK:
        t.post(f"/profiles/{pid}/events", json={"kind": kind, "year": y, "month": m, "day": d})
    t.post(f"/profiles/{pid}/events", json={"kind": "child", "year": 1983})
    d = _admin().get("/admin/api/events").json()
    assert d["charts"] == 1 and d["events"] == 8 and d["fits"] >= 6 and d["lift"] > 1.3
    assert {r["topic"] for r in d["by_topic"]} >= {"marriage", "property", "vehicle"}
    assert t.get("/admin/api/events").status_code == 403
