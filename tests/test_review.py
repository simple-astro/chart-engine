"""Studio Review: queue order, saving a review, validation and who may review."""
import pytest
from fastapi.testclient import TestClient

from app import access, review, storage
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
PASS = {k: "pass" for k, _ in review.CHECKS}
RPASS = {k: "pass" for k, _ in review.REMEDY_CHECKS}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code, nxt="/admin"):
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303
    return c


def _log(pid, question, kind="llm", caught=False):
    storage.log_usage(pid, kind, question, model="claude-haiku-4-5", answer="Asha ji, a steady period.",
                      owner=storage.get(pid)["owner"],
                      factcheck={"found": ["Said Mars rules the 10th"] if caught else [], "removed": [], "revised": caught})
    return storage.recent_queries(1)[0]["id"] if kind != "playground" else None


def test_queue_order_and_reviews_drop_out(env):
    pid = _login("tester-code", "/").post("/profiles", json=BODY).json()["id"]
    career1 = _log(pid, "When will my career improve?")
    career2 = _log(pid, "Will I get a new job offer?")
    caught = _log(pid, "When will I get married to my partner?", caught=True)
    _log(pid, "How is my career going?", kind="cache")
    _log(pid, "Is my job safe?", kind="playground")
    more = [_log(pid, f"Will my job contract number {i} be renewed?") for i in range(30)]
    owner = _login("admin-code")
    q = owner.get("/admin/api/review/queue").json()
    ids = [i["id"] for i in q["items"]]
    assert ids[0] == caught and q["items"][0]["reason"] == "caught"
    first_topic = [i for i in q["items"] if i["reason"] == "new_topic"]
    assert career1 in [i["id"] for i in first_topic] and career2 not in [i["id"] for i in first_topic]
    sample = [i["id"] for i in q["items"] if i["reason"] == "sample"]
    assert sample == sorted([x for x in more + [career2] if review.sampled(x)], reverse=True)
    assert q["counts"]["total"] == len(ids) and q["items"][0]["tester"].startswith("Tester ")

    r = owner.post(f"/admin/api/review/{career1}", json={"checks": PASS, "note": "Good"})
    assert r.status_code == 201 and r.json()["reviewer"] == "Owner"
    assert owner.post(f"/admin/api/review/{career1}", json={"checks": PASS}).status_code == 409
    after = owner.get("/admin/api/review/queue").json()["items"]
    assert career1 not in [i["id"] for i in after]
    # career is covered now, so no other career answer is "first on its topic"
    assert not [i for i in after if i["reason"] == "new_topic" and "Career & job" in i["topics"]]
    assert owner.get("/admin/api/audit").json()[0]["action"] == "reviewed an answer"


def test_review_card_and_validation(env):
    pid = _login("tester-code", "/").post("/profiles", json=BODY).json()["id"]
    uid = _log(pid, "When will my career improve?")
    owner = _login("admin-code")
    mentor = owner.post("/admin/api/team", json={"label": "Guruji", "role": "mentor"}).json()
    meera = _login(owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer"}).json()["code"])
    card = meera.get(f"/admin/api/review/{uid}").json()
    assert card["chart"]["lagna"] and card["chart"]["dasha"][0]["level"] == "maha"
    assert card["chart"]["facts"].startswith("{") and card["review"] is None
    bad = meera.post(f"/admin/api/review/{uid}", json={"checks": {**PASS, "timing": None}})
    assert bad.status_code == 422 and "Timing" in bad.json()["detail"]
    fail = {**PASS, "facts": "fail"}
    assert meera.post(f"/admin/api/review/{uid}", json={"checks": fail}).status_code == 422   # say what went wrong
    assert meera.post(f"/admin/api/review/{uid}", json={"checks": fail, "tags": ["Nope"]}).status_code == 422
    ok = meera.post(f"/admin/api/review/{uid}", json={"checks": {**fail, "timing": "na"}, "tags": ["Wrong house"]})
    assert ok.status_code == 201 and ok.json()["reviewer"] == "Meera" and ok.json()["checks"]["timing"] == "na"
    assert meera.get(f"/admin/api/review/{uid}").json()["review"]["tags"] == ["Wrong house"]
    done = _login(mentor["code"]).get("/admin/api/reviews").json()
    assert done[0]["usage_id"] == uid and done[0]["tester"].startswith("Tester ")
    assert meera.get("/admin/api/review/999").status_code == 404


def test_testers_cannot_review(env):
    t = _login("tester-code", "/")
    assert t.get("/admin/api/review/queue").status_code in (401, 403)


def test_remedy_questions_get_the_remedy_checks(env):
    pid = _login("tester-code", "/").post("/profiles", json=BODY).json()["id"]
    uid = _log(pid, "Which remedies help my Saturn period?")
    owner = _login("admin-code")
    card = owner.get(f"/admin/api/review/{uid}").json()
    assert card["check_set"] == "remedy" and [c["key"] for c in card["checks"]] == ["fits", "safe", "habits", "gems", "tone"]
    assert owner.post(f"/admin/api/review/{uid}", json={"checks": PASS}).status_code == 422      # the reading checks
    r = owner.post(f"/admin/api/review/{uid}", json={"checks": {**RPASS, "gems": "fail"}, "tags": ["Gem without substitute"]})
    assert r.status_code == 201
    done = owner.get("/admin/api/reviews").json()[0]
    assert done["check_set"] == "remedy" and done["checks_done"]["gems"] == "fail"
    assert "failed: Gems only with a substitute" in owner.get("/admin/api/audit").json()[0]["detail"]
