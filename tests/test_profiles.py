"""Saved profiles + ask endpoint."""
import pytest
from fastapi.testclient import TestClient

from app import ask
from app.main import app

BODY = {"name": "T", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209,
        "tz_name": "Asia/Kolkata"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return TestClient(app)


def test_profile_roundtrip(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    assert client.get("/profiles").json()[0]["name"] == "T"
    assert client.get(f"/profiles/{pid}").json()["chart"]["lagna"]["sign"] == "Virgo"
    assert client.delete(f"/profiles/{pid}").status_code == 200
    assert client.get(f"/profiles/{pid}").status_code == 404


def test_lookup_questions(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    for q, expect in [("Where is my Moon?", "Capricorn"), ("current dasha", "Mahadasha"),
                      ("show house 7", "House 7"), ("what is my lagna", "Virgo")]:
        r = client.post(f"/profiles/{pid}/ask", json={"question": q}).json()
        assert r["mode"] == "lookup" and expect in r["answer"], q


def test_open_question_without_key_is_503(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    r = client.post(f"/profiles/{pid}/ask", json={"question": "How is my career outlook?"})
    assert r.status_code == 503


def test_llm_context_is_valid_json(client):
    import json
    p = client.get(f"/profiles/{client.post('/profiles', json=BODY).json()['id']}").json()
    assert json.loads(ask._llm_context(p))["lagna"]["sign"] == "Virgo"
