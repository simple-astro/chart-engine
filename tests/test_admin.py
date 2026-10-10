"""Admin page: sign-in, settings that drive the chat, caps, and the question log."""
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import access, chat
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209,
        "tz_name": "Asia/Kolkata"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    for var in ("CHART_LLM_MODEL", "CHAT_DAILY_LIMIT_PER_TESTER", "CHAT_DAILY_LIMIT_TOTAL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    access._fails.clear()
    yield
    access._fails.clear()


def _tester() -> TestClient:
    c = TestClient(app)
    assert c.post("/login", data={"code": "tester-code"}, follow_redirects=False).status_code == 303
    return c


def _admin(c: TestClient | None = None) -> TestClient:
    c = c or TestClient(app)
    r = c.post("/login", data={"code": "admin-code", "next": "/admin"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    return c


class FakeStream:
    def __init__(self, text="Your career looks steady.", stop="end_turn"):
        self.text_stream, self._stop = [text], stop

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def get_final_message(self):
        return NS(stop_reason=self._stop, content=[], model=None,
                  usage=NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0))


@pytest.fixture
def fake_llm(monkeypatch):
    calls = {"plain": [], "beta": []}
    state = {"stop": "end_turn"}

    def maker(kind):
        def stream(**kw):
            calls[kind].append(kw)
            return FakeStream(stop=state["stop"])
        return NS(stream=stream)

    monkeypatch.setattr(chat, "_client", lambda: NS(messages=maker("plain"), beta=NS(messages=maker("beta"))))
    return calls, state


def test_admin_page_asks_for_the_admin_code(gated):
    assert "Admin code" in TestClient(app).get("/admin").text
    t = _tester()
    assert "Admin code" in t.get("/admin").text  # a tester browser can reach the admin form
    assert t.get("/admin/api/overview").status_code == 403


def test_tester_code_on_admin_form_is_refused(gated):
    r = TestClient(app).post("/login", data={"code": "tester-code", "next": "/admin"}, follow_redirects=False)
    assert r.status_code == 401 and "tester code" in r.text


def test_admin_sign_in_from_a_tester_browser_keeps_their_charts(gated):
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    _admin(t)
    assert "Settings" in t.get("/admin").text
    assert [p["id"] for p in t.get("/profiles").json()] == [pid]
    assert t.get("/me").json() == {"admin": True, "gated": True}
    # signing in again with the tester code does not drop admin
    t.post("/login", data={"code": "tester-code"}, follow_redirects=False)
    assert t.get("/admin/api/overview").status_code == 200


def test_next_only_allows_known_pages(gated):
    r = TestClient(app).post("/login", data={"code": "admin-code", "next": "https://evil.example"},
                             follow_redirects=False)
    assert r.headers["location"] == "/"


def test_settings_roundtrip_and_validation(gated):
    a = _admin()
    s = a.get("/admin/api/overview").json()["settings"]
    assert s == {"model": "claude-haiku-4-5", "word_limit": 300, "daily_limit_per_tester": 30,
                 "daily_limit_total": 300, "telegram_daily_limit": 5}
    new = {"model": "claude-sonnet-5-5", "word_limit": 200, "daily_limit_per_tester": 5, "daily_limit_total": 50,
           "telegram_daily_limit": 3}
    assert a.put("/admin/api/settings", json=new).json() == new
    for bad in ({"model": "gpt-4"}, {"word_limit": 20}, {"daily_limit_total": -1}, {"word_limit": True},
                {"word_limit": "300"}, {"nope": 1}, {"model": "claude-opus-5-5", "word_limit": 5}):
        assert a.put("/admin/api/settings", json=bad).status_code == 422, bad
    assert a.get("/admin/api/overview").json()["settings"] == new  # rejected saves changed nothing
    assert _tester().put("/admin/api/settings", json=new).status_code == 403


def test_haiku_request_shape(gated, fake_llm):
    calls, _ = fake_llm
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    kw = calls["plain"][0]
    assert kw["model"] == "claude-haiku-4-5" and kw["max_tokens"] == 1500 and not calls["beta"]
    assert "HARD LIMIT of 300 words" in kw["system"][0]["text"]


def test_newer_model_request_shape_and_word_limit(gated, fake_llm):
    calls, _ = fake_llm
    _admin().put("/admin/api/settings", json={"model": "claude-opus-5-5", "word_limit": 150})
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    kw = calls["beta"][0]
    assert kw["model"] == "claude-opus-5-5" and kw["max_tokens"] == chat.MAX_TOKENS_THINKING
    assert kw["output_config"] == {"effort": "low"} and kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"] and "thinking" not in kw
    assert "HARD LIMIT of 150 words" in kw["system"][0]["text"]


def test_refusal_gets_a_friendly_reply(gated, fake_llm):
    _, state = fake_llm
    state["stop"] = "refusal"
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    r = t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"}).json()
    assert "can't help with that question" in r["reply"]


def test_caps_come_from_admin_settings(gated, fake_llm):
    _admin().put("/admin/api/settings", json={"daily_limit_per_tester": 1})
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    assert t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"}).status_code == 200
    assert t.post(f"/profiles/{pid}/chat", json={"message": "What about my marriage prospects?"}).status_code == 429


def test_question_log_and_costs(gated, fake_llm):
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    a = _admin()
    [row] = a.get("/admin/api/queries").json()
    assert row["question"] == "How is my career outlook?" and row["answer"] == "Your career looks steady."
    assert row["profile_name"] == "Asha" and row["tester"].startswith("Tester ") and "owner" not in row
    assert row["cost"] == pytest.approx((1000 * 1.0 + 200 * 5.0) / 1e6)  # Haiku 4.5 rates
    o = a.get("/admin/api/overview").json()
    assert o["today"]["paid_questions"] == 1 and o["today"]["cost"] == pytest.approx(0.002)
    assert o["charts"] == 1 and len(o["testers"]) == 1 and o["testers"][0]["owner"] is None
    assert o["testers"][0]["chart_names"] == "Asha" and o["testers"][0]["questions_today"] == 1
    assert _tester().get("/admin/api/queries").status_code == 403


def test_local_mode_admin_is_open(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("TESTER_ACCESS_CODES", raising=False)
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    c = TestClient(app)
    assert "Settings" in c.get("/admin").text and c.get("/admin/api/overview").status_code == 200
    assert c.get("/me").json() == {"admin": True, "gated": False}


def test_admin_can_add_remarks_to_questions(gated, fake_llm):
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    a = _admin()
    [q] = a.get("/admin/api/queries").json()
    assert q.get("admin_remarks") is None
    r = a.put(f"/admin/api/queries/{q['id']}/remarks", json={"remarks": "Strong 10th house - monitor Saturn transit"})
    assert r.status_code == 200
    [q] = a.get("/admin/api/queries").json()
    assert q["admin_remarks"] == "Strong 10th house - monitor Saturn transit"
    r = a.put(f"/admin/api/queries/{q['id']}/remarks", json={"remarks": ""})
    assert r.status_code == 200
    [q] = a.get("/admin/api/queries").json()
    assert q.get("admin_remarks") is None or q["admin_remarks"] == ""


def test_remarks_are_injected_into_system_prompt(gated, fake_llm):
    calls, _ = fake_llm
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    a = _admin()
    [q] = a.get("/admin/api/queries").json()
    a.put(f"/admin/api/queries/{q['id']}/remarks", json={"remarks": "Previous observation: very practical person"})
    t.post(f"/profiles/{pid}/chat", json={"message": "What about finances?"})
    kw = calls["plain"][1]  # second call
    assert "Previous observation: very practical person" in kw["system"][0]["text"]


def test_remarks_only_visible_to_admin(gated, fake_llm):
    t = _tester()
    pid = t.post("/profiles", json=BODY).json()["id"]
    t.post(f"/profiles/{pid}/chat", json={"message": "How is my career outlook?"})
    _admin(t)  # upgrade tester to admin (same browser/session)
    [q] = t.get("/admin/api/queries").json()
    t.put(f"/admin/api/queries/{q['id']}/remarks", json={"remarks": "Secret note"})
    t2 = _tester()  # new tester browser
    assert t2.get("/admin/api/queries").status_code == 403


def _login(code: str) -> tuple[TestClient, int]:
    c = TestClient(app)
    return c, c.post("/login", data={"code": code}, follow_redirects=False).status_code


def test_admin_creates_codes_and_testers_can_use_them(gated):
    a = _admin()
    made = a.post("/admin/api/codes", json={"label": "Asha's family"}).json()
    assert made["code"].startswith("sj-") and len(made["code"]) == 11 and made["active"]
    custom = a.post("/admin/api/codes", json={"label": "Workshop", "code": "workshop-2026"}).json()
    assert custom["code"] == "workshop-2026"
    t, status = _login(made["code"])
    assert status == 303 and t.get("/profiles").status_code == 200
    pid = t.post("/profiles", json=BODY).json()["id"]
    [row] = [c for c in a.get("/admin/api/codes").json()["codes"] if c["id"] == made["id"]]
    assert row["uses"] == 1 and row["testers"] == 1 and row["last_used"]
    assert a.get("/admin/api/overview").json()["testers"][0]["label"].startswith("Asha's family · ")
    assert _tester().get("/profiles").status_code == 200  # the environment code still works
    assert pid


def test_paused_or_deleted_code_ends_access(gated):
    a = _admin()
    code = a.post("/admin/api/codes", json={"label": "Temp"}).json()
    t, _ = _login(code["code"])
    assert t.get("/profiles").status_code == 200
    assert a.patch(f"/admin/api/codes/{code['id']}", json={"active": False}).status_code == 200
    assert "turned off" in t.get("/").text  # the page explains why, then the cookie is cleared
    t, _ = _login("tester-code")
    t.cookies.set(access.COOKIE, access.make_session("b" * 32, False, code["id"]))
    r = t.get("/profiles")
    assert r.status_code == 401 and "turned off" in r.json()["detail"]
    assert _login(code["code"])[1] == 401  # can't sign in again while paused
    a.patch(f"/admin/api/codes/{code['id']}", json={"active": True, "label": "Back again"})
    t, status = _login(code["code"])
    assert status == 303 and t.get("/profiles").status_code == 200
    assert a.delete(f"/admin/api/codes/{code['id']}").status_code == 200
    assert t.get("/profiles").status_code == 401
    assert a.delete(f"/admin/api/codes/{code['id']}").status_code == 404


def test_code_validation_and_admin_only(gated):
    a = _admin()
    for bad in ({"code": "abc"}, {"code": "has space!"}, {"label": "x" * 61}, {"label": 5}):
        assert a.post("/admin/api/codes", json=bad).status_code == 422, bad
    assert a.post("/admin/api/codes", json={"code": "tester-code"}).status_code == 409  # env code
    assert a.post("/admin/api/codes", json={"code": "admin-code"}).status_code == 409
    a.post("/admin/api/codes", json={"code": "dupe-code-1"})
    assert a.post("/admin/api/codes", json={"code": "dupe-code-1"}).status_code == 409
    t = _tester()
    assert t.get("/admin/api/codes").status_code == 403
    assert t.post("/admin/api/codes", json={}).status_code == 403
    assert t.delete("/admin/api/codes/1").status_code == 403


def test_questions_per_day_can_be_raised_for_one_code(gated, fake_llm):
    a = _admin()
    a.put("/admin/api/settings", json={"daily_limit_per_tester": 1})
    vip = a.post("/admin/api/codes", json={"label": "Family"}).json()
    other = a.post("/admin/api/codes", json={"label": "Friends"}).json()
    assert vip["daily_limit"] is None and a.get("/admin/api/codes").json()["default_limit"] == 1
    assert a.patch(f"/admin/api/codes/{vip['id']}", json={"daily_limit": 3}).status_code == 200
    t, _ = _login(vip["code"])
    pid = t.post("/profiles", json=BODY).json()["id"]
    for q in ("How is my career?", "And my marriage?", "What about money?"):
        assert t.post(f"/profiles/{pid}/chat", json={"message": q}).status_code == 200
    assert t.post(f"/profiles/{pid}/chat", json={"message": "And my health?"}).status_code == 429
    [row] = [c for c in a.get("/admin/api/codes").json()["codes"] if c["id"] == vip["id"]]
    assert row["daily_limit"] == 3 and row["asked_today"] == 3
    o, _ = _login(other["code"])  # other codes keep the default of 1
    pid2 = o.post("/profiles", json=BODY).json()["id"]
    assert o.post(f"/profiles/{pid2}/chat", json={"message": "How is my career?"}).status_code == 200
    assert o.post(f"/profiles/{pid2}/chat", json={"message": "And my marriage?"}).status_code == 429
    # back to the default, and validation
    assert a.patch(f"/admin/api/codes/{vip['id']}", json={"daily_limit": None}).status_code == 200
    assert [c for c in a.get("/admin/api/codes").json()["codes"] if c["id"] == vip["id"]][0]["daily_limit"] is None
    for bad in (-1, 1001, 2.5, "10", True):
        assert a.patch(f"/admin/api/codes/{vip['id']}", json={"daily_limit": bad}).status_code == 422
    assert t.patch(f"/admin/api/codes/{vip['id']}", json={"daily_limit": 99}).status_code == 403
