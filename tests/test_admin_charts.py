"""Admin › Saved charts: the owner, mentors and astrologers see users' birth details; testers don't; every look is logged."""
import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app

BIRTH = {"name": "Test Person", "place": "Delhi, India", "dob": "1990-03-15", "tob": "06:20:00", "lat": 28.6139,
         "lon": 77.209, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code: str, nxt: str = "/") -> TestClient:
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303
    return c


def test_team_sees_birth_details_and_each_look_is_logged(gated):
    tester = _login("tester-code")
    pid = tester.post("/profiles", json=BIRTH).json()["id"]
    owner = _login("admin-code", "/admin")
    mentor = owner.post("/admin/api/team", json={"label": "Guruji", "role": "mentor"}).json()
    m = _login(mentor["code"], "/admin")
    astro = m.post("/admin/api/team", json={"label": "Meera"}).json()
    a = _login(astro["code"], "/admin")
    for who in (owner, m, a):
        rows = who.get("/admin/api/charts").json()
        row = next(r for r in rows if r["id"] == pid)
        assert (row["name"], row["dob"], row["tob"], row["place"], row["tz_name"]) == \
            ("Test Person", "1990-03-15", "06:20", "Delhi, India", "Asia/Kolkata")
        d = who.get(f"/admin/api/charts/{pid}").json()
        assert d["summary"]["lagna"] and d["summary"]["dasha"] and d["lat"] == 28.6139
    log = owner.get("/admin/api/audit").json()
    seen = [(x["actor"], x["action"], x["object"]) for x in log if x["action"] == "viewed birth details"]
    assert ("Meera", "viewed birth details", "Test Person") in seen and ("Guruji", "viewed birth details", "Test Person") in seen


def test_testers_cannot_see_other_peoples_birth_details(gated):
    tester = _login("tester-code")
    assert tester.get("/admin/api/charts").status_code in (401, 403)
    assert tester.get("/admin/api/charts/1").status_code in (401, 403)


def test_unknown_chart_is_404(gated):
    owner = _login("admin-code", "/admin")
    assert owner.get("/admin/api/charts/999").status_code == 404
