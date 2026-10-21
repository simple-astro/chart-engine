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
    # D150 (Chandra Kala Nadi), its Lagna birth-time window, and the KP houses for the dasha-lords table
    assert set(body["vargas"]["D150"]) == set(body["grahas"]) and 0 <= body["varga_lagna"]["D150"] < 12
    assert body["nadi_amsha"]["counting"] == "Chandra Kala Nadi" and body["nadi_amsha"]["lagna_window"]["later"] >= 1
    assert set(body["kp_houses"]) == set(body["grahas"]) and all(body["kp_houses"]["Sun"])


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


def test_transit_scan_endpoint_returns_sorted_events():
    r = client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30 and isinstance(body["events"], list)
    times = [e["exact_at"] for e in body["events"]]
    assert times == sorted(times)
    for e in body["events"]:
        assert set(e.keys()) == {"type", "planet", "exact_at", "detail"}
        assert e["type"] in ("ingress", "station", "nakshatra_change", "eclipse")


def test_transit_scan_days_out_of_range_422():
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 0}).status_code == 422
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 99}).status_code == 422
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 32}).status_code == 422
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 31}).status_code == 200


def test_chart_with_pushya_paksha_ayanamsha():
    """Pushya Paksha shifts every position by about 1.13 deg against Lahiri, keeps Placidus cusps for KP/Nadi."""
    body = {"dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
    p = client.post("/chart", json={**body, "ayanamsha": "pushya"})
    assert p.status_code == 200, p.text
    l = client.post("/chart", json={**body, "ayanamsha": "lahiri"}).json()
    p = p.json()
    assert p["meta"]["ayanamsha"] == "pushya"
    shift = (p["grahas"]["Sun"]["longitude"] - l["grahas"]["Sun"]["longitude"]) % 360
    assert abs(shift - 1.13) < 0.02
    assert len({round(h["longitude"] % 30, 3) for h in p["houses"]}) > 1  # Placidus cusps, not whole-sign
    assert client.post("/chart", json={**body, "ayanamsha": "made_up"}).status_code == 422


def test_old_time_zone_names_still_work():
    """Android reports Asia/Calcutta; the tzdata package keeps such aliases working on slim servers."""
    import importlib.util
    assert importlib.util.find_spec("tzdata") is not None
    body = {"dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Calcutta"}
    assert client.post("/chart", json=body).status_code == 200


def test_dasha_year_and_ashtakavarga_settings():
    from fastapi.testclient import TestClient
    from datetime import datetime
    from app.main import app
    from core import ashtakavarga as A
    c = TestClient(app)
    base = {"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata"}
    solar = c.post("/chart", json=base).json()
    savana = c.post("/chart", json={**base, "dasha_year": "savana", "ashtakavarga": "varahamihira"}).json()
    assert "dasha_year" not in solar["meta"] and savana["meta"]["dasha_year"] == "savana"
    days = lambda ch, i: (datetime.fromisoformat(ch["dasha"][i]["end"]) - datetime.fromisoformat(ch["dasha"][i]["start"])).days
    for i in (1, 2):  # whole Mahadashas: years x days per year
        assert abs(days(solar, i) / days(savana, i) - 365.25 / 360) < 0.001
    assert solar["ashtakavarga"]["method"] == "parashara" and savana["ashtakavarga"]["method"] == "varahamihira"
    assert solar["ashtakavarga"]["bav_totals"] == savana["ashtakavarga"]["bav_totals"]
    t = A.table("varahamihira")
    assert 9 in t["Moon"]["Moon"] and 9 not in t["Moon"]["Mars"] and 2 in t["Moon"]["Jupiter"]
    assert 12 not in t["Moon"]["Jupiter"] and 4 in t["Venus"]["Mars"] and 5 not in t["Venus"]["Mars"]
    assert A.table("parashara") is A.BENEFIC
    span = lambda p: (datetime.fromisoformat(p["end"]) - datetime.fromisoformat(p["start"])).days
    assert abs(span(solar["narayana"]["periods"][1]) / span(savana["narayana"]["periods"][1]) - 365.25 / 360) < 0.01
    assert c.post("/chart", json={**base, "dasha_year": "lunar"}).status_code == 422
