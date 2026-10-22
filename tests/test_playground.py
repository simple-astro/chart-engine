"""Studio Playground: test settings for one run, the daily budget, drafts and the shared limits."""
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import access, chat, storage
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


class FakeStream:
    def __init__(self, text):
        self.text_stream, self._text = [text], text

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def get_final_message(self):
        return NS(stop_reason="end_turn", content=[], model=None,
                  usage=NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0, cache_creation_input_tokens=0))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    for var in ("CHART_LLM_MODEL", "CHAT_WORD_LIMIT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    calls = []

    def stream(**kw):
        calls.append(kw)
        return FakeStream("Your career looks steady in this period.")
    monkeypatch.setattr(chat, "_client", lambda: NS(messages=NS(stream=stream), beta=NS(messages=NS(stream=stream))))
    access._fails.clear()
    yield calls
    access._fails.clear()


def _login(code, nxt="/admin"):
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303
    return c


def _system(kw) -> str:
    return "".join(b["text"] for b in kw["system"])


def test_owner_runs_live_and_test_side_by_side_without_changing_live(env):
    t = _login("tester-code", "/")
    pid = t.post("/profiles", json=BODY).json()["id"]
    owner = _login("admin-code")
    r = owner.post("/admin/api/playground", json={"profile_id": pid, "question": "How is my career this year?",
        "variants": [{}, {"label": "Shorter", "word_limit": 150, "instruction": "Always mention the 10th lord."}]})
    assert r.status_code == 200, r.text
    live, test = r.json()["results"]
    assert live["label"] == "Live" and test["label"] == "Shorter" and live["text"] and live["words"] > 0
    assert live["seen"]["chart_facts"].startswith("{") and live["seen"]["word_limit"] == 300
    assert test["seen"]["word_limit"] == 150 and test["seen"]["instruction"] == "Always mention the 10th lord."
    systems = [_system(kw) for kw in env]
    assert any("HARD LIMIT of 150 words" in s and "Always mention the 10th lord." in s for s in systems)
    assert any("HARD LIMIT of 300 words" in s and "Always mention" not in s for s in systems)
    assert r.json()["chart"]["tester"].startswith("Tester ")
    # experiments stay out of the testers' question log and tester counts; live settings unchanged
    assert owner.get("/admin/api/queries").json() == []
    assert owner.get("/admin/api/playground").json()["live"]["word_limit"] == 300


def test_saved_charts_only(env):
    owner = _login("admin-code")
    for body in ({"birth": BODY}, {}, {"profile_id": 999}, {"profile_id": "x"}):
        r = owner.post("/admin/api/playground", json={**body, "question": "When will I marry?"})
        assert r.status_code == 404 and r.json()["detail"] == "Pick a saved chart"


def test_astrologer_budget_is_enforced(env):
    owner = _login("admin-code")
    astro = owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer", "daily_limit": 1}).json()
    a = _login(astro["code"])
    pid = _login("tester-code", "/").post("/profiles", json=BODY).json()["id"]
    assert a.get("/admin/api/playground").json()["budget"] == {"limited": True, "limit": 1, "used": 0, "left": 1}
    two = a.post("/admin/api/playground", json={"profile_id": pid, "question": "Career?", "variants": [{}, {}]})
    assert two.status_code == 429                                          # two versions need two answers
    assert a.post("/admin/api/playground", json={"profile_id": pid, "question": "Career?"}).status_code == 200
    again = a.post("/admin/api/playground", json={"profile_id": pid, "question": "Career?"})
    assert again.status_code == 429 and "1 of 1" in again.json()["detail"]
    assert owner.get("/admin/api/playground").json()["budget"] == {"limited": False}


def test_drafts_and_validation(env):
    owner = _login("admin-code")
    astro = owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer"}).json()
    a = _login(astro["code"])
    d = a.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Marriage & love",
                                                 "text": "Always look at the Upapada as well as the 7th."})
    assert d.status_code == 201 and d.json()["author"] == "Meera" and d.json()["status"] == "draft"
    assert a.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Nope", "text": "x" * 20}).status_code == 422
    assert a.post("/admin/api/studio/drafts", json={"kind": "rule", "text": "x" * 20}).status_code == 422
    assert [x["kind"] for x in a.get("/admin/api/studio/drafts").json()] == ["lesson"]
    assert owner.get("/admin/api/audit").json()[0]["action"] == "saved a draft lesson"


def test_admin_changes_limits_astrologer_cannot(env):
    owner = _login("admin-code")
    mentor = owner.post("/admin/api/team", json={"label": "Guruji", "role": "mentor"}).json()
    astro = owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer"}).json()
    m, a = _login(mentor["code"]), _login(astro["code"])
    r = m.put("/admin/api/limits", json={"word_limit": 350, "daily_limit_per_tester": 20})
    assert r.status_code == 200 and r.json()["word_limit"] == 350
    log = m.get("/admin/api/audit").json()[0]
    assert log["actor"] == "Guruji" and "word limit 300 → 350" in log["detail"]
    # the whole Limits form saves in one go, including the critic, the consult link and Varshaphal AI polishing
    form = {"word_limit": 350, "daily_limit_per_tester": 20, "daily_limit_total": 300, "telegram_daily_limit": 5,
            "consult_telegram": "", "critic": "auto", "varshaphal_ai": "everyone"}
    r = m.put("/admin/api/limits", json=form)
    assert r.status_code == 200 and r.json()["varshaphal_ai"] == "everyone"
    assert "Varshaphal AI polishing studio → everyone" in m.get("/admin/api/audit").json()[0]["detail"]
    assert m.put("/admin/api/limits", json={"model": "claude-opus-4-1"}).status_code == 422   # model is the owner's
    assert m.put("/admin/api/limits", json={"word_limit": 5}).status_code == 422
    assert a.put("/admin/api/limits", json={"word_limit": 400}).status_code == 403
