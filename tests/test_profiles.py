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


def _pid(client):
    return client.post("/profiles", json=BODY).json()["id"]


def test_chat_without_key_answers_simple_lookups(client):
    pid = _pid(client)
    r = client.post(f"/profiles/{pid}/chat", json={"message": "Where is my Moon?"}).json()
    assert r["mode"] == "lookup" and "Capricorn" in r["reply"]
    assert [m["role"] for m in client.get(f"/profiles/{pid}/chat").json()] == ["user", "assistant"]


def test_chat_open_question_without_key_is_503(client):
    pid = _pid(client)
    r = client.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    assert r.status_code == 503
    assert client.get(f"/profiles/{pid}/chat").json() == []  # failed turns are not stored


def test_chat_tool_loop_and_history(client, monkeypatch):
    from types import SimpleNamespace as NS
    from app import chat

    calls = []

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            if len(calls) == 1:
                return NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t1", name="get_transits", input={})])
            return NS(stop_reason="end_turn", content=[NS(type="text", text="Saturn is in your 5th.")])

    monkeypatch.setattr(chat, "_client", lambda: NS(messages=FakeMessages()))
    pid = _pid(client)
    r = client.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"}).json()
    assert r == {"mode": "llm", "reply": "Saturn is in your 5th."}
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "house_from_lagna" in tool_result["content"]
    client.post(f"/profiles/{pid}/chat", json={"message": "And marriage?"})
    assert len(calls[2]["messages"]) == 3  # prior user+assistant turn is sent as history
    assert client.delete(f"/profiles/{pid}/chat").status_code == 200
    assert client.get(f"/profiles/{pid}/chat").json() == []


def test_tools_run_against_engine(client):
    from app import chat, storage
    pid = _pid(client)
    p = storage.get(pid)
    assert "Saturn" in chat.run_tool(p, "get_transits", {"when": "2026-10-05T00:00:00"})["grahas"]
    assert chat.run_tool(p, "get_panchang", {"date": "2026-10-05"})["tithi"]
    assert "D10" in chat.run_tool(p, "get_divisional_chart", {"name": "d10"})
    assert chat.run_tool(p, "get_dasha_detail", {"mahadasha": "rahu"})["lord"] == "Rahu"
    assert isinstance(chat.run_tool(p, "get_transit_events", {"days": 7})["events"], list)


def test_llm_context_is_valid_json(client):
    import json
    p = client.get(f"/profiles/{_pid(client)}").json()
    assert json.loads(ask.llm_context(p))["lagna"]["sign"] == "Virgo"
