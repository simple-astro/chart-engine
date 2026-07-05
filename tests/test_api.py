"""HTTP endpoint tests via FastAPI TestClient."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CHART_BODY = {
    "name": "Reference One",
    "dob": "1990-08-15",
    "tob": "12:00:00",
    "lat": 28.6139,
    "lon": 77.2090,
    "tz_name": "Asia/Kolkata",
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_version():
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["engine_version"]
    assert body["default_ayanamsha"] == "krishnamurti"


def test_chart_endpoint():
    r = client.post("/chart", json=CHART_BODY)
    assert r.status_code == 200
    body = r.json()
    assert len(body["grahas"]) == 9
    assert body["meta"]["house_system"] == "placidus"
    assert "ascendant" in body["lagna"]


def test_chart_endpoint_rejects_bad_timezone():
    bad = dict(CHART_BODY, tz_name="Not/AZone")
    r = client.post("/chart", json=bad)
    assert r.status_code == 422


def test_panchang_endpoint():
    r = client.post("/panchang", json={
        "on": "2000-01-01", "lat": 28.6139, "lon": 77.2090, "tz_name": "Asia/Kolkata",
    })
    assert r.status_code == 200
    body = r.json()
    assert 1 <= body["tithi"]["number"] <= 30
    assert body["weekday"] == "Saturday"


def test_transits_endpoint():
    r = client.post("/transits", json={"when": "2020-03-20T12:00:00+00:00"})
    assert r.status_code == 200
    assert len(r.json()["grahas"]) == 9
