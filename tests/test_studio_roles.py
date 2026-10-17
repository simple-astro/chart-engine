"""Studio roles: the owner, a mentor and astrologers each reach only their own parts of Admin."""
import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code: str, nxt: str = "/admin") -> TestClient:
    c = TestClient(app)
    r = c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False)
    assert r.status_code == 303, r.text[:200]
    return c


def _team(owner: TestClient):
    mentor = owner.post("/admin/api/team", json={"label": "Guruji", "role": "mentor"}).json()
    return mentor, _login(mentor["code"])


def test_owner_makes_a_mentor_who_sees_costs_and_studio_but_not_owner_settings(gated):
    owner = _login("admin-code")
    mentor, m = _team(owner)
    assert mentor["role"] == "mentor" and mentor["daily_limit"] == 30
    assert "Admin" in m.get("/admin").text or m.get("/admin").status_code == 200
    me = m.get("/me").json()
    assert me["role"] == "mentor" and me["name"] == "Guruji" and me["admin"] is False
    for path in ("/admin/api/overview", "/admin/api/usage", "/admin/api/queries", "/admin/api/team", "/admin/api/audit"):
        assert m.get(path).status_code == 200, path
    for path in ("/admin/api/codes", "/admin/api/backups", "/admin/api/remedies", "/admin/api/profiles"):
        assert m.get(path).status_code == 403, path
    assert m.put("/admin/api/settings", json={"word_limit": 500}).status_code == 403


def test_a_mentor_can_make_astrologers_but_never_more_access(gated):
    owner = _login("admin-code")
    mentor, m = _team(owner)
    other, _ = _team(owner)
    assert m.post("/admin/api/team", json={"label": "X", "role": "mentor"}).status_code == 403
    assert m.post("/admin/api/codes", json={"label": "tester"}).status_code == 403
    astro = m.post("/admin/api/team", json={"label": "Meera", "daily_limit": 20}).json()
    assert astro["role"] == "astrologer" and astro["daily_limit"] == 20 and astro["created_by"] == mentor["id"]
    assert m.patch(f"/admin/api/team/{other['id']}", json={"active": False}).status_code == 403   # another mentor
    assert m.delete(f"/admin/api/team/{other['id']}").status_code == 403
    assert [c["label"] for c in m.get("/admin/api/team").json()["codes"]] == ["Meera"]           # astrologers only
    log = m.get("/admin/api/audit").json()
    assert (log[0]["actor"], log[0]["actor_role"], log[0]["action"], log[0]["object"]) == \
        ("Guruji", "mentor", "created an astrologer code", "Meera")


def test_an_astrologer_sees_questions_only_and_pausing_ends_access_at_once(gated):
    owner = _login("admin-code")
    _, m = _team(owner)
    astro = m.post("/admin/api/team", json={"label": "Meera"}).json()
    a = _login(astro["code"])
    assert a.get("/me").json()["role"] == "astrologer"
    assert a.get("/admin/api/queries").status_code == 200
    for path in ("/admin/api/overview", "/admin/api/team", "/admin/api/audit", "/admin/api/codes", "/admin/api/usage"):
        assert a.get(path).status_code == 403, path
    assert a.post("/admin/api/team", json={"label": "Y"}).status_code == 403
    assert m.patch(f"/admin/api/team/{astro['id']}", json={"active": False}).status_code == 200
    assert a.get("/admin/api/queries").status_code == 401                  # paused: out on the next request
    assert m.get("/admin/api/audit").json()[0]["detail"] == "paused"


def test_tester_codes_still_cannot_open_admin(gated):
    c = TestClient(app)
    r = c.post("/login", data={"code": "tester-code", "next": "/admin"}, follow_redirects=False)
    assert r.status_code == 401 and "tester code" in r.text
    t = _login("tester-code", "/")
    assert t.get("/admin/api/queries").status_code == 403 and t.get("/me").json()["role"] == "tester"


def test_team_needs_a_name_and_a_sane_budget(gated):
    owner = _login("admin-code")
    assert owner.post("/admin/api/team", json={"label": "", "role": "astrologer"}).status_code == 422
    assert owner.post("/admin/api/team", json={"label": "A", "daily_limit": 5000}).status_code == 422
    assert owner.post("/admin/api/team", json={"label": "A", "role": "admin"}).status_code == 422
    assert owner.get("/admin/api/codes").json()["codes"] == []             # Studio codes are not tester codes
