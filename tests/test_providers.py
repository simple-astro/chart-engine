"""Other LLM providers (OpenAI, Gemini) through the OpenAI-compatible API, and the admin model comparison."""
import json
from types import SimpleNamespace as NS

import pytest

from app import chat, config, storage
from tests.test_admin import BODY, _admin, _tester, fake_llm, gated  # noqa: F401  (fixtures)


def _resp(text=None, calls=None, reason="stop", prompt=900, cached=300, out=150):
    tc = [NS(id=f"call_{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(calls or [])]
    return NS(choices=[NS(message=NS(content=text, tool_calls=tc or None), finish_reason=reason)],
              usage=NS(prompt_tokens=prompt, completion_tokens=out, prompt_tokens_details=NS(cached_tokens=cached)))


@pytest.fixture
def fake_compat(monkeypatch):
    """A stand-in OpenAI-compatible client: first asks for the panchang tool, then answers."""
    seen = []
    script = {"replies": [_resp(calls=[("get_panchang", {"date": "2026-10-10"})], reason="tool_calls"),
                          _resp("Saturday is for routine work; wear dark blue.")]}

    def create(**kw):
        seen.append(kw)
        return script["replies"].pop(0) if script["replies"] else _resp("Saturday is for routine work.")
    monkeypatch.setattr(chat, "_compat_client", lambda provider: NS(chat=NS(completions=NS(create=create))))
    return seen, script


def test_models_list_providers_and_prices():
    for mid, m in config.MODELS.items():
        assert m["provider"] in config.PROVIDERS and m["in"] > 0 and m["out"] > 0
    assert {config.provider_of(m) for m in config.MODELS} == {"anthropic", "openai", "gemini"}
    assert config.cost("gpt-6-luna", 1_000_000, 1_000_000, 0, 0) == pytest.approx(0.60)


def test_a_model_needs_its_providers_key(gated, monkeypatch):
    a = _admin()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = a.put("/admin/api/settings", json={"model": "gpt-6-luna"})
    assert r.status_code == 422 and "OPENAI_API_KEY" in r.json()["detail"]
    assert a.get("/admin/api/overview").json()["providers"]["openai"]["ready"] is False
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    assert a.put("/admin/api/settings", json={"model": "gpt-6-luna"}).status_code == 200
    assert config.model() == "gpt-6-luna"


def test_chat_runs_tools_and_the_fact_check_on_another_provider(gated, fake_compat, monkeypatch):
    seen, _ = fake_compat
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    _admin().put("/admin/api/settings", json={"model": "gemini-3.8-flash"})
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    r = t.post(f"/profiles/{pid}/chat", json={"message": "Is Saturday 10 October a good day for me?"}).json()
    assert r["mode"] == "llm" and "routine" in r["reply"]
    first, second = seen
    assert first["model"] == "gemini-3.8-flash" and first["messages"][0]["role"] == "system"
    assert {t["function"]["name"] for t in first["tools"]} >= {"get_panchang", "get_kp_prediction"}
    assert "max_tokens" in first  # Gemini's endpoint; OpenAI takes max_completion_tokens
    tool_msg = second["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_0" and "local_times" in tool_msg["content"]
    row = storage.recent_queries(1)[0]
    assert row["model"] == "gemini-3.8-flash" and row["input_tokens"] == 2 * 600 and row["cache_read_tokens"] == 600


def test_compare_two_models_side_by_side(gated, fake_llm, fake_compat, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    a = _admin()
    pid = _tester().post("/profiles", json=BODY).json()["id"]
    assert any(p["id"] == pid for p in a.get("/admin/api/profiles").json())
    r = a.post("/admin/api/compare", json={"profile_id": pid, "question": "How is my career looking this year?",
                                           "models": ["claude-haiku-4-5", "gpt-6-luna"]})
    assert r.status_code == 200
    res = {x["model"]: x for x in r.json()["results"]}
    assert res["claude-haiku-4-5"]["text"] == "Your career looks steady."
    assert "routine" in res["gpt-6-luna"]["text"] and res["gpt-6-luna"]["tools"] == ["get_panchang"]
    assert all(x["cost"] is not None and x["seconds"] >= 0 and "factcheck" in x for x in res.values())
    assert storage.get_messages(pid) == []  # nothing lands in the user's chat
    assert {q["kind"] for q in storage.recent_queries(5)} == {"compare"}
    assert storage.llm_requests_today() == 0  # comparisons don't use up testers' daily questions
    bad = a.post("/admin/api/compare", json={"profile_id": pid, "question": "Career?", "models": ["gemini-3.8-flash"]})
    assert bad.status_code == 422 and "GEMINI_API_KEY" in bad.json()["detail"]
    assert _tester().post("/admin/api/compare", json={}).status_code == 403
