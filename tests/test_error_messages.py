"""User-facing errors: a bad timezone gets a structured, friendly 422 and no endpoint returns exception text."""
import json

import pytest
from fastapi.testclient import TestClient

from app import chat
from app.main import app
from app.routes import TZ_ERROR

BODY = {"name": "T", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209,
        "tz_name": "Asia/Kolkata"}
BAD = "Foo/Bar"
WHERE = {"lat": 28.6139, "lon": 77.209, "tz_name": BAD}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return TestClient(app)


def _is_tz_error(r):
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == TZ_ERROR
    assert "No time zone found" not in r.text and "key" not in r.json()["detail"]["message"]


@pytest.mark.parametrize("path", ["/chart", "/profiles", "/lal-kitab", "/birth-extras"])
def test_bad_timezone_on_the_chart_form(client, path):
    _is_tz_error(client.post(path, json={**BODY, "tz_name": BAD}))


def test_bad_timezone_when_editing_a_profile(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    _is_tz_error(client.put(f"/profiles/{pid}", json={**BODY, "tz_name": BAD}))


@pytest.mark.parametrize("path,body", [
    ("/panchang", {**WHERE, "on": "2026-10-19"}),
    ("/muhurat", {**WHERE, "start": "2026-10-19"}),
    ("/muhurat/find", {**WHERE, "activity": "marriage", "start": "2026-10-19"}),
    ("/today", {**WHERE, "date": "2026-10-19", "lagna_sign": 0, "birth_nakshatra": 0, "birth_moon_sign": 0}),
    ("/jamakkol", {**WHERE, "kind": "general"}),
])
def test_bad_timezone_on_other_endpoints(client, path, body):
    _is_tz_error(client.post(path, json=body))


def test_bad_timezone_in_query_strings(client):
    _is_tz_error(client.get("/lagna-times", params={"lat": 28.6, "lon": 77.2, "tz": BAD}))
    pid = client.post("/profiles", json=BODY).json()["id"]
    _is_tz_error(client.get(f"/profiles/{pid}/transit", params={"tz": BAD}))


def test_other_calculation_failures_hide_the_exception(client, monkeypatch):
    from app import routes

    def boom(_):
        raise RuntimeError("swe_calc internal error at jd 2451545")
    monkeypatch.setattr(routes, "compute_natal_chart", boom)
    r = client.post("/chart", json=BODY)
    assert r.status_code == 422 and r.json()["detail"] == routes.CALC_ERROR and "swe_calc" not in r.text


def test_unknown_activity_is_a_plain_message(client):
    r = client.post("/muhurat/find", json={**WHERE, "tz_name": "Asia/Kolkata", "activity": "nope", "start": "2026-10-19"})
    assert r.status_code == 422 and "nope" not in r.text


def test_chat_errors_hide_server_details(client, monkeypatch):
    pid = client.post("/profiles", json=BODY).json()["id"]

    def broken(*a, **k):
        raise RuntimeError("ANTHROPIC_API_KEY is not set on the server. Add it to .env and restart.")
        yield  # pragma: no cover
    monkeypatch.setattr(chat, "chat_events", broken)
    monkeypatch.setattr(chat, "chat", lambda *a, **k: broken().__next__())
    s = client.post(f"/profiles/{pid}/chat/stream", json={"message": "How is my career?"})
    err = [json.loads(l) for l in s.text.splitlines()][-1]
    assert err["type"] == "error" and "ANTHROPIC" not in err["detail"] and "try again" in err["detail"]
    r = client.post(f"/profiles/{pid}/chat", json={"message": "How is my career?"})
    assert r.status_code == 503 and "ANTHROPIC" not in r.text
