"""Tester access gate: codes, private per-browser spaces, admin-only usage, daily caps."""
import pytest
from fastapi.testclient import TestClient

from app import access, storage
from app.main import app

BODY = {"name": "T", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209,
        "tz_name": "Asia/Kolkata"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code, second-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code="tester-code") -> TestClient:
    c = TestClient(app)
    r = c.post("/login", data={"code": code}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return c


def test_everything_but_health_is_locked(gated):
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert "Access code" in c.get("/").text
    for path in ("/profiles", "/usage", "/profiles/1/chat"):
        assert c.get(path).status_code == 401
    assert c.post("/chart", json=BODY).status_code == 401


def test_wrong_code_is_refused(gated):
    c = TestClient(app)
    r = c.post("/login", data={"code": "nope"}, follow_redirects=False)
    assert r.status_code == 401 and "isn't right" in r.text
    assert c.get("/profiles").status_code == 401


def test_any_listed_code_works(gated):
    assert _login("second-code").get("/profiles").json() == []


def test_testers_cannot_see_each_others_data(gated):
    a, b = _login(), _login()
    pid = a.post("/profiles", json=BODY).json()["id"]
    a.post(f"/profiles/{pid}/chat", json={"message": "Where is my Moon?"})

    assert [p["id"] for p in a.get("/profiles").json()] == [pid]
    assert b.get("/profiles").json() == []
    assert b.get(f"/profiles/{pid}").status_code == 404
    assert b.get(f"/profiles/{pid}/chat").status_code == 404
    assert b.post(f"/profiles/{pid}/chat", json={"message": "Where is my Moon?"}).status_code == 404
    assert b.delete(f"/profiles/{pid}/chat").status_code == 404
    assert b.delete(f"/profiles/{pid}").status_code == 404
    mine = b.post("/profiles", json=BODY).json()["id"]
    assert b.post("/matchmaking", json={"groom_id": mine, "bride_id": pid}).status_code == 404
    # A's data is untouched by B's attempts
    assert a.get(f"/profiles/{pid}").status_code == 200
    assert len(a.get(f"/profiles/{pid}/chat").json()) == 2


def test_chat_tools_only_see_own_profiles(gated):
    from app import chat
    a, b = _login(), _login()
    a_pid = a.post("/profiles", json=BODY).json()["id"]
    b_pid = b.post("/profiles", json={**BODY, "name": "B"}).json()["id"]
    b_profile = b.get(f"/profiles/{b_pid}").json()
    assert chat.run_tool(b_profile, "list_profiles", {}) == {"profiles": []}
    with pytest.raises(Exception):
        chat.run_tool(b_profile, "match_with_profile", {"partner_id": a_pid, "native_role": "groom"})


def test_usage_is_admin_only(gated):
    assert _login().get("/usage").status_code == 403
    assert _login("admin-code").get("/usage").status_code == 200


def test_logging_in_again_keeps_the_same_private_space(gated):
    a = _login()
    pid = a.post("/profiles", json=BODY).json()["id"]
    assert a.post("/login", data={"code": "tester-code"}, follow_redirects=False).status_code == 303
    assert [p["id"] for p in a.get("/profiles").json()] == [pid]


def test_tampered_cookie_is_rejected(gated):
    a = _login()
    owner, admin, sig = a.cookies[access.COOKIE].split(".")
    forged = TestClient(app)
    forged.cookies.set(access.COOKIE, f"{owner}.1.{sig}")  # try to promote to admin
    assert forged.get("/usage").status_code == 401
    forged.cookies.set(access.COOKIE, f"someone-else.0.{sig}")
    assert forged.get("/profiles").status_code == 401


def test_daily_cap_per_tester(gated, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT_PER_TESTER", "1")
    a, b = _login(), _login()
    pid = a.post("/profiles", json=BODY).json()["id"]
    profile = a.get(f"/profiles/{pid}").json()
    storage.log_usage(pid, "llm", "q", owner=profile["owner"])
    r = a.post(f"/profiles/{pid}/chat/stream", json={"message": "How is my career?"})
    assert r.status_code == 429 and "limit" in r.json()["detail"]
    b_pid = b.post("/profiles", json=BODY).json()["id"]  # another tester is unaffected
    assert b.post(f"/profiles/{b_pid}/chat", json={"message": "Where is my Moon?"}).status_code == 200


def test_daily_cap_total(gated, monkeypatch):
    monkeypatch.setenv("CHAT_DAILY_LIMIT_TOTAL", "1")
    a = _login()
    pid = a.post("/profiles", json=BODY).json()["id"]
    storage.log_usage(pid, "llm", "q", owner="someone-else")
    assert a.post(f"/profiles/{pid}/chat", json={"message": "Where is my Moon?"}).status_code == 429


def test_repeated_wrong_codes_are_throttled(gated):
    c = TestClient(app)
    for _ in range(access.FAIL_PER_IP):
        c.post("/login", data={"code": "wrong"})
    r = c.post("/login", data={"code": "tester-code"}, follow_redirects=False)
    assert r.status_code == 429


def test_gate_off_without_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("TESTER_ACCESS_CODES", raising=False)
    monkeypatch.delenv("ADMIN_ACCESS_CODE", raising=False)
    c = TestClient(app)
    assert "SimpleJyotish" in c.get("/").text and c.get("/profiles").status_code == 200
    assert c.get("/usage").status_code == 200
