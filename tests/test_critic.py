"""The critic: a second small AI read for tone and policy on sensitive questions, feeding the one correction pass."""
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import chat, config, critic, storage
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
GOOD = ("Asha ji, your Moon's nakshatra favours steady, patient effort at work, so a rise comes slowly. Do: keep a "
        "fixed routine and help an elder on Saturdays. Don't: switch jobs on impulse.")
DOOM = GOOD + " Your marriage will definitely fail because of this Saturn period."
USE = {"input": 500, "output": 60, "cache_read": 0, "cache_write": 0}


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("CHAT_CRITIC", raising=False)
    pid = TestClient(app).post("/profiles", json=BODY).json()["id"]
    return storage.get(pid)


def run(profile, monkeypatch, message, text, verdict, fixed=GOOD):
    calls = {"review": 0, "revise": []}

    def review(question, draft, model=critic.MODEL):
        calls["review"] += 1
        if isinstance(verdict, Exception):
            raise verdict
        return verdict, USE

    def revise(profile, history, msg, draft, note, model=None):
        calls["revise"].append(note)
        return fixed, USE
    monkeypatch.setattr(critic, "review", review)
    monkeypatch.setattr(chat, "revise", revise)
    out = [e for e in chat.guard(profile, [], message, text, []) if e["type"] == "checked"][0]
    return out, calls


def test_when_it_runs():
    assert critic.wanted("off", "Will my marriage work?") is None
    assert critic.wanted("always", "What is my lagna?") == "every answer"
    assert critic.wanted("auto", "Will my marriage work?") == "Marriage & love"
    assert critic.wanted("auto", "Should I invest in stocks now?") == "Money"
    assert critic.wanted("auto", "How long will I live?") == "sensitive words"
    assert critic.wanted("auto", "What does my Moon nakshatra mean?") is None


def test_a_clean_sensitive_answer_costs_one_small_call(profile, monkeypatch):
    out, calls = run(profile, monkeypatch, "Will my marriage work?", GOOD, {"verdict": "ok", "problems": []})
    assert calls == {"review": 1, "revise": []} and out["text"] == GOOD
    assert out["report"]["critic"] == {"why": "Marriage & love", "verdict": "ok", "problems": [], "revised": False}
    assert out["usage"] == USE                                   # the critic's tokens are counted with the answer


def test_a_flagged_draft_is_rewritten_once_through_the_same_pass(profile, monkeypatch):
    v = {"verdict": "revise", "problems": [{"type": "certainty", "detail": "\"will definitely fail\""},
                                           {"type": "fear", "detail": "doom about the Saturn period"}]}
    out, calls = run(profile, monkeypatch, "Will my marriage work?", DOOM, v)
    assert len(calls["revise"]) == 1 and "will definitely fail" in calls["revise"][0]
    assert "tendencies" in calls["revise"][0] and "fear or doom" in calls["revise"][0]
    assert out["text"] == GOOD and out["report"]["critic"]["revised"] is True
    assert out["usage"]["input"] == 1000                         # critic call + rewrite


def test_a_rewrite_that_contradicts_the_chart_is_not_kept(profile, monkeypatch):
    v = {"verdict": "revise", "problems": [{"type": "tone", "detail": "cold"}]}
    bad = "Asha ji, your Moon is in Aries, in the 5th house, exalted. Do: rest. Don't: rush."
    out, calls = run(profile, monkeypatch, "Will my marriage work?", GOOD, v, fixed=bad)
    assert out["text"] == GOOD and out["report"]["critic"]["revised"] is False
    assert "contradicted the chart" in out["report"]["critic"]["rejected"]


def test_off_and_non_sensitive_questions_never_call_it(profile, monkeypatch):
    out, calls = run(profile, monkeypatch, "How is my career?", GOOD, {"verdict": "ok", "problems": []})
    assert calls["review"] == 0 and "critic" not in out["report"]
    config.update({"critic": "off"})
    out, calls = run(profile, monkeypatch, "Will my marriage work?", GOOD, {"verdict": "ok", "problems": []})
    assert calls["review"] == 0
    config.update({"critic": "always"})
    out, calls = run(profile, monkeypatch, "How is my career?", GOOD, {"verdict": "ok", "problems": []})
    assert calls["review"] == 1


def test_a_failing_critic_never_blocks_the_answer(profile, monkeypatch):
    out, calls = run(profile, monkeypatch, "Will my marriage work?", GOOD, RuntimeError("no key"))
    assert out["text"] == GOOD and "critic" not in out["report"] and calls["revise"] == []


def test_review_parses_and_sanitises_the_reply(monkeypatch):
    reply = ('{"verdict": "revise", "problems": [{"type": "advice", "detail": "tells them to stop medicine"}, '
             '{"type": "made-up", "detail": "x"}, "junk"]}')
    fake = NS(messages=NS(create=lambda **kw: NS(content=[NS(text=reply)], usage=NS(input_tokens=700, output_tokens=50))))
    monkeypatch.setattr(chat, "_client", lambda: fake)
    v, use = critic.review("Should I stop my medicine?", "Yes, stop it.")
    assert v == {"verdict": "revise", "problems": [{"type": "advice", "detail": "tells them to stop medicine"}]}
    assert use["input"] == 700
    fake.messages.create = lambda **kw: NS(content=[NS(text='{"verdict": "revise", "problems": []}')], usage=None)
    assert critic.review("q", "a")[0]["verdict"] == "ok"        # "revise" with nothing to fix is "ok"
    fake.messages.create = lambda **kw: NS(content=[NS(text="not json")], usage=None)
    assert critic.review("q", "a")[0] == {"verdict": "ok", "problems": []}
