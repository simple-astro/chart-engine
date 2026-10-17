"""Studio › Remedies: astrologers add and suggest, the Admin (mentor) and owner approve; live items stay live."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app
from app.remedies import library

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remedies_fixture.json").read_text())["items"]
ARGHYA = {k: v for k, v in next(i for i in FIXTURE if i.get("slug") == "sun-arghya").items() if k not in ("kind", "slug")}
NEW = {"planet": "Saturn", "type": "seva", "source": "folk", "intent": ["pacify"], "cost_tier": "free", "effort": 2,
       "title": "Help an elder on Saturdays", "steps": ["Spend an hour helping an elderly neighbour on Saturday."],
       "why_template": "{planet} is your {role}; quiet service to elders softens it."}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code):
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": "/admin"}, follow_redirects=False).status_code == 303
    return c


def _team():
    owner = _login("admin-code")
    owner.post("/admin/api/remedies/import", json={"items": FIXTURE})
    owner.patch("/admin/api/remedies/remedy/sun-arghya", json={"review_status": "approved"})
    codes = [owner.post("/admin/api/team", json={"label": n, "role": r}).json()["code"]
             for n, r in (("Guruji", "mentor"), ("Meera", "astrologer"), ("Ravi", "astrologer"))]
    return owner, *[_login(c) for c in codes]


def test_astrologer_suggests_a_change_and_the_live_remedy_stays_until_accepted(env):
    owner, mentor, meera, ravi = _team()
    assert meera.get("/admin/api/remedies").status_code == 200
    r = meera.patch("/admin/api/remedies/remedy/sun-arghya", json={"data": {**ARGHYA, "effort": 2}})
    assert r.status_code == 200 and r.json()["review_status"] == "approved" and r.json()["effort"] == 1
    assert r.json()["proposal"]["by"] == "Meera" and r.json()["proposal"]["data"]["effort"] == 2
    assert [i["effort"] for i in library.served("remedy")] == [1]                  # users keep the approved one
    assert meera.post("/admin/api/remedies/remedy/sun-arghya/proposal/accept").status_code == 403
    assert ravi.post("/admin/api/remedies/remedy/sun-arghya/proposal/discard").status_code == 403
    a = mentor.post("/admin/api/remedies/remedy/sun-arghya/proposal/accept").json()
    assert a["effort"] == 2 and a["version"] == 2 and a["review_status"] == "approved" and "proposal" not in a
    assert [i["effort"] for i in library.served("remedy")] == [2]
    assert owner.get("/admin/api/audit").json()[0]["action"] == "accepted a suggested remedy change"
    # a bad suggestion is refused with the reason; whoever suggested can withdraw theirs
    bad = meera.patch("/admin/api/remedies/remedy/sun-arghya", json={"data": {**ARGHYA, "steps": ["Use ivory."]}})
    assert bad.status_code == 422 and "banned" in bad.json()["detail"]
    meera.patch("/admin/api/remedies/remedy/sun-arghya", json={"data": {**ARGHYA, "effort": 3}})
    assert "proposal" not in meera.post("/admin/api/remedies/remedy/sun-arghya/proposal/discard").json()


def test_new_items_wait_for_review_and_only_approvers_approve(env):
    owner, mentor, meera, _ = _team()
    r = meera.post("/admin/api/remedies", json={"kind": "remedy", "data": NEW})
    assert r.status_code == 201 and r.json()["slug"] == "saturn-help-an-elder-on-saturdays"
    assert r.json()["review_status"] == "pending_astrologer"
    assert meera.post("/admin/api/remedies", json={"kind": "remedy", "data": NEW}).json()["slug"].endswith("-2")
    assert meera.post("/admin/api/remedies", json={"kind": "remedy", "data": {**NEW, "type": "ratna"}}).status_code == 422
    slug = r.json()["slug"]
    assert "saturn" not in {i["planet"].lower() for i in library.served("remedy")}
    assert meera.patch(f"/admin/api/remedies/remedy/{slug}", json={"review_status": "approved"}).status_code == 403
    # an astrologer's edit to a draft simply updates it
    e = meera.patch(f"/admin/api/remedies/remedy/{slug}", json={"data": {**NEW, "effort": 1}})
    assert e.json()["effort"] == 1 and e.json()["review_status"] == "pending_astrologer" and "proposal" not in e.json()
    assert mentor.patch(f"/admin/api/remedies/remedy/{slug}", json={"review_status": "approved"}).status_code == 200
    assert slug in [i["slug"] for i in library.served("remedy")]
    # importing the seed file stays with the owner; the Admin can export
    assert mentor.post("/admin/api/remedies/import", json={"items": FIXTURE}).status_code == 403
    assert mentor.get("/admin/api/remedies/export").status_code == 200
    assert meera.get("/admin/api/remedies/export").status_code == 403
    actions = [e["action"] for e in owner.get("/admin/api/audit").json()]
    assert "added a remedy item" in actions and "approved a remedy item" in actions
