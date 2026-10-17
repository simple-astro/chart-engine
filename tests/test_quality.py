"""Studio Quality: the test set, runs judged against gold answers, per-topic scores and the publish gate."""
import json
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import access, chat, quality, storage
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
USAGE = NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0, cache_creation_input_tokens=0)
BAD = "Always answer career questions in one line."


class FakeStream:
    def __init__(self, text):
        self.text_stream = [text]

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def get_final_message(self):
        return NS(stop_reason="end_turn", content=[], model=None, usage=USAGE)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    for var in ("CHART_LLM_MODEL", "CHAT_WORD_LIMIT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    turns = []

    def stream(**kw):  # the answer: short when the bad lesson is in the teaching
        turns.append(kw["messages"][-1]["content"])
        return FakeStream("Short." if BAD in turns[-1] else "Asha ji, a steady rise is likely; keep a calm daily routine.")

    def create(**kw):  # the judge: fails the short answer
        short = "ANSWER TO GRADE:\nShort." in kw["messages"][0]["content"]
        checks = {k: ("fail" if short and k in ("method", "action") else "pass")
                  for k in ("facts", "method", "timing", "tone", "action")}
        return NS(content=[NS(text=json.dumps({"checks": checks, "note": "ok"}))], usage=USAGE)
    monkeypatch.setattr(chat, "_client", lambda: NS(messages=NS(stream=stream, create=create),
                                                    beta=NS(messages=NS(stream=stream))))
    access._fails.clear()
    yield turns
    access._fails.clear()


def _login(code, nxt="/admin"):
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303
    return c


def _setup():
    pid = _login("tester-code", "/").post("/profiles", json=BODY).json()["id"]
    owner = _login("admin-code")
    golds = []
    for q, a in (("When will I get a promotion at my job?", "Asha ji, Saturn as 10th lord gives a rise in 2027."),
                 ("Should I change my career this year?", "Asha ji, stay steady until the Jupiter antardasha.")):
        g = owner.post("/admin/api/studio/drafts", json={"kind": "gold", "topic": "Career & job", "text": a,
                                                         "question": q, "profile_id": pid}).json()
        assert owner.post(f"/admin/api/studio/drafts/{g['id']}/publish").status_code == 200
        golds.append(g)
    return owner, pid, golds


def test_test_set_and_a_live_run(env):
    owner, pid, golds = _setup()
    meera = _login(owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer"}).json()["code"])
    assert meera.post(f"/admin/api/quality/test-set/{golds[0]['id']}", json={"on": True}).status_code == 403
    draft = owner.post("/admin/api/studio/drafts", json={"kind": "gold", "topic": "Money", "text": "Asha ji, steady.",
                                                         "question": "Will I be rich?", "profile_id": pid}).json()
    assert owner.post(f"/admin/api/quality/test-set/{draft['id']}", json={"on": True}).status_code == 422  # not published
    for g in golds:
        assert owner.post(f"/admin/api/quality/test-set/{g['id']}", json={"on": True}).json()["in_test_set"] == 1
    home = meera.get("/admin/api/quality").json()
    assert len(home["test_set"]) == 2 and home["estimate"]["answers"] == 2 and home["estimate"]["cost"] > 0

    run = owner.post("/admin/api/quality/runs", json={}).json()
    quality.wait(run["id"], 10)
    r = meera.get(f"/admin/api/quality/runs/{run['id']}").json()
    assert r["status"] == "done" and r["done"] == 2 and r["cost"] > 0
    assert r["scores"]["overall"]["live"] == 10.0 and r["scores"]["topics"]["Career & job"]["n"] == 2
    assert all(i["gold"] and i["judge"]["checks"]["facts"] == "pass" for i in r["items"])
    # a test question never sees its own gold answer as an example
    for g in golds:
        turn = next(t for t in env if t.startswith(g["question"]))
        assert g["text"] not in turn
    # people can mark a test answer next to the judge
    item = r["items"][0]
    assert meera.post(f"/admin/api/quality/items/{item['id']}/grade",
                      json={"checks": {k: "fail" for k in ("facts", "method", "timing", "tone", "action")}}).status_code == 422
    ok = meera.post(f"/admin/api/quality/items/{item['id']}/grade",
                    json={"checks": {k: "pass" for k in ("facts", "method", "timing", "tone", "action")}})
    assert ok.status_code == 200
    assert storage.get_eval_item(item["id"])["human_by"] == "Meera"
    assert meera.get("/admin/api/quality").json()["dashboard"]["scores"][0]["score"] == 10.0
    assert owner.get("/admin/api/overview").json()["today"]["studio_cost"] >= r["cost"]
    assert storage.recent_queries(10) == []                  # runs stay out of the testers' log


def test_publish_gate_asks_twice_when_the_score_drops(env):
    owner, pid, golds = _setup()
    for g in golds:
        owner.post(f"/admin/api/quality/test-set/{g['id']}", json={"on": True})
    bad = owner.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Career & job", "text": BAD}).json()
    first = owner.post(f"/admin/api/studio/drafts/{bad['id']}/publish")
    assert first.status_code == 409 and first.json()["detail"]["code"] == "needs_gate"
    gate = owner.post(f"/admin/api/quality/gate/{bad['id']}").json()
    quality.wait(gate["id"], 10)
    g = storage.get_run(gate["id"])
    assert g["scores"]["topics"]["Career & job"]["live"] == 10.0 and g["scores"]["topics"]["Career & job"]["draft"] < 9
    second = owner.post(f"/admin/api/studio/drafts/{bad['id']}/publish")
    assert second.status_code == 409 and second.json()["detail"]["code"] == "drop"
    assert second.json()["detail"]["topics"] == ["Career & job"]
    third = owner.post(f"/admin/api/studio/drafts/{bad['id']}/publish", json={"confirm_drop": True})
    assert third.status_code == 200
    assert "score dropped" in owner.get("/admin/api/audit").json()[0]["detail"]
    # a lesson on a topic with no test questions publishes straight away
    other = owner.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Health",
                                                         "text": "For health, suggest a doctor first."}).json()
    assert owner.post(f"/admin/api/studio/drafts/{other['id']}/publish").status_code == 200


def test_one_run_at_a_time_and_limits(env):
    owner, _, golds = _setup()
    assert owner.post("/admin/api/quality/runs", json={}).status_code == 422          # no test questions yet
    owner.post(f"/admin/api/quality/test-set/{golds[0]['id']}", json={"on": True})
    storage.add_run("run", None, [], 0, "claude-haiku-4-5", quality.JUDGE_MODEL, 1, "Owner")  # left running
    assert owner.post("/admin/api/quality/runs", json={}).status_code == 409
    assert owner.get("/admin/api/quality").json()["running"]["status"] == "running"
