"""Log out ends the session, yet the same code on the same browser gets its private charts back."""
import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app

BIRTH = {"name": "Kept Chart", "place": "Delhi, India", "dob": "1990-03-15", "tob": "06:20:00", "lat": 28.6139,
         "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code,other-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(c: TestClient, code: str, nxt: str = "/") -> None:
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303


def test_logout_ends_the_session(gated):
    c = TestClient(app)
    _login(c, "tester-code")
    assert c.get("/profiles").status_code == 200
    assert c.post("/logout").status_code == 204
    assert c.get("/profiles").status_code == 401
    assert "Access code" in c.get("/").text  # back to the sign-in page


def test_same_code_gets_the_same_charts_back(gated):
    c = TestClient(app)
    _login(c, "tester-code")
    pid = c.post("/profiles", json=BIRTH).json()["id"]
    c.post("/logout")
    _login(c, "tester-code")
    assert [p["id"] for p in c.get("/profiles").json()] == [pid]


def test_another_persons_code_never_gets_those_charts(gated):
    owner = TestClient(app)
    _login(owner, "admin-code", "/admin")
    a = owner.post("/admin/api/codes", json={"label": "Asha"}).json()["code"]
    b = owner.post("/admin/api/codes", json={"label": "Ravi"}).json()["code"]
    c = TestClient(app)                          # one shared browser
    _login(c, a)
    c.post("/profiles", json=BIRTH)
    c.post("/logout")
    _login(c, b)
    assert c.get("/profiles").json() == []       # Ravi does not get Asha's charts
    c.post("/logout")
    _login(c, a)
    assert [p["name"] for p in c.get("/profiles").json()] == ["Kept Chart"]


def test_logout_without_a_session_is_harmless(gated):
    assert TestClient(app).post("/logout").status_code == 204


def test_a_forged_space_cookie_is_ignored(gated):
    c = TestClient(app)
    c.cookies.set(access.space_cookie("tester", 0), "victim.tester.0." + "0" * 64)
    _login(c, "tester-code")
    assert c.get("/profiles").json() == []


def test_log_out_in_the_app_and_admin_pages():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "app" / "static"
    index, admin = (root / "index.html").read_text(), (root / "admin.html").read_text()
    assert 'id="mlogout"' in index and "fetch('/logout',{method:'POST'})" in index and "m.gated)$('mlogout')" in index
    assert 'id="logout"' in admin and "fetch('/logout'" in admin
