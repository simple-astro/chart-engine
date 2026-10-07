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


def test_profile_keeps_birthplace(client):
    pid = client.post("/profiles", json={**BODY, "place": "New Delhi, Delhi, India"}).json()["id"]
    assert client.get(f"/profiles/{pid}").json()["request"]["place"] == "New Delhi, Delhi, India"
    old = client.post("/profiles", json=BODY).json()["id"]
    assert client.get(f"/profiles/{old}").json()["request"]["place"] == ""


def test_profile_edit_updates_in_place(client):
    pid = client.post("/profiles", json=BODY).json()["id"]
    r = client.put(f"/profiles/{pid}", json={**BODY, "name": "T2", "tob": "06:00:00", "place": "Delhi"})
    assert r.status_code == 200 and r.json()["name"] == "T2"
    assert [p["id"] for p in client.get("/profiles").json()] == [pid]  # no duplicate
    p = client.get(f"/profiles/{pid}").json()
    assert p["request"]["tob"] == "06:00:00" and p["chart"]["lagna"]["sign"] != "Virgo"
    assert client.put("/profiles/9999", json=BODY).status_code == 404


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

    class FakeStream:
        def __init__(self, resp, texts):
            self.resp, self.text_stream = resp, texts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return self.resp

    class FakeMessages:
        def stream(self, **kw):
            calls.append(kw)
            if len(calls) == 1:
                return FakeStream(NS(stop_reason="tool_use",
                                     content=[NS(type="tool_use", id="t1", name="get_transits", input={})]), [])
            return FakeStream(NS(stop_reason="end_turn", content=[]), ["Saturn is ", "in your 5th."])

    monkeypatch.setattr(chat, "_client", lambda: NS(messages=FakeMessages()))
    pid = _pid(client)
    r = client.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"}).json()
    assert r == {"mode": "llm", "reply": "Saturn is in your 5th."}
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "house_from_lagna" in tool_result["content"]
    resp = client.post(f"/profiles/{pid}/chat/stream", json={"message": "And marriage?"})
    import json as _j
    evs = [_j.loads(l) for l in resp.text.splitlines()]
    assert evs[-1] == {"type": "done", "mode": "llm"} and "".join(e.get("text", "") for e in evs) == "Saturn is in your 5th."
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
    rahu = chat.run_tool(p, "get_dasha_detail", {"mahadasha": "rahu"})
    assert rahu["maha"] == "Rahu" and all(x["maha"] == "Rahu" and x["pratyantar"] for x in rahu["periods"])
    assert isinstance(chat.run_tool(p, "get_transit_events", {"days": 7})["events"], list)


def test_llm_context_is_valid_json(client):
    import json
    p = client.get(f"/profiles/{_pid(client)}").json()
    assert json.loads(ask.llm_context(p))["lagna"]["sign"] == "Virgo"


def test_limit_words_cuts_on_line_boundary():
    from app.chat import limit_words
    text = "\n".join(f"- point {i} " + "word " * 9 for i in range(60))  # 600 words
    out = limit_words(text, 300)
    assert 0 < len(out.split()) <= 300 and out.splitlines()[-1].startswith("- point")
    assert limit_words("short answer", 300) == "short answer"


def test_cache_key_rules():
    from app.chat import cache_key
    assert cache_key("How is my career outlook?") == "how is my career outlook"
    assert cache_key("Why?") is None and cache_key("tell me more about that please") is None


def test_answer_reuse_and_usage_log(client, monkeypatch):
    from types import SimpleNamespace as NS
    from app import chat
    n = []

    class S:
        def __init__(self): self.text_stream = ["Career looks steady."]
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get_final_message(self):
            return NS(stop_reason="end_turn", content=[],
                      usage=NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=0,
                               cache_creation_input_tokens=0))

    class M:
        def stream(self, **kw):
            n.append(kw)
            return S()

    monkeypatch.setattr(chat, "_client", lambda: NS(messages=M()))
    pid = _pid(client)
    r1 = client.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"}).json()
    r2 = client.post(f"/profiles/{pid}/chat", json={"message": "how is my CAREER outlook"}).json()
    assert (r1["mode"], r2["mode"]) == ("llm", "cache") and r1["reply"] == r2["reply"]
    assert len(n) == 1  # the second ask never reached the model
    assert n[0]["model"] == "claude-haiku-4-5" and n[0]["max_tokens"] == 1500
    u = client.get("/usage").json()
    assert u["by_kind"]["llm"]["input_tokens"] == 100 and u["by_kind"]["cache"]["requests"] == 1
