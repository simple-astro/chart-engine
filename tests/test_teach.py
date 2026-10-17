"""Studio Teach: the fixed rules, publish / retire / rollback with versions, and teaching reaching answers."""
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import access, chat, storage, teach
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
CAREER = "For career questions, always name the 10th lord and the house it sits in."
MARRIAGE = "For marriage questions, always look at the Upapada as well as the 7th house."


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


def _turn(kw) -> str:
    return kw["messages"][-1]["content"]


def _team(owner):
    mentor = owner.post("/admin/api/team", json={"label": "Guruji", "role": "mentor"}).json()
    meera = owner.post("/admin/api/team", json={"label": "Meera", "role": "astrologer"}).json()
    ravi = owner.post("/admin/api/team", json={"label": "Ravi", "role": "astrologer"}).json()
    return _login(mentor["code"]), _login(meera["code"]), _login(ravi["code"])


def test_fixed_rules():
    assert teach.check(CAREER) == [] and teach.check(MARRIAGE) == []
    assert teach.check("Never predict divorce or death; say it gently.") == []
    assert teach.check("Saturn here is dangerous and brings bad luck.")[0].startswith("No fear wording")
    assert "death" in teach.check("The 8th lord shows the age of death.")[0]
    assert "divorce" in teach.check("Mars in the 7th means divorce.")[0]
    assert teach.check("Ask them to chant the Shani mantra 108 times.")[0].startswith("No mantra japa")
    assert teach.check("Give a Saturn mantra only if the user asks for one; chant it softly.") == []
    assert "substitute" in teach.check("Wear a blue sapphire on Saturday.")[0]
    assert teach.check("A blue sapphire only with a substitute (amethyst) and after you consult an astrologer.") == []
    assert teach.check("Never suggest a gemstone first.") == []


def test_publish_reaches_the_next_answer_on_its_topic_and_rollback_restores(env):
    t = _login("tester-code", "/")
    pid = t.post("/profiles", json=BODY).json()["id"]
    owner = _login("admin-code")
    mentor, meera, _ = _team(owner)
    a = meera.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Career & job", "text": CAREER}).json()
    b = meera.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Marriage & love", "text": MARRIAGE}).json()
    assert a["status"] == "draft" and a["author_code"]

    # drafts never reach users; astrologers can't publish
    t.post(f"/profiles/{pid}/chat", json={"message": "How will my career go this year?"})
    assert CAREER not in _turn(env[-1])
    assert meera.post(f"/admin/api/studio/drafts/{a['id']}/publish").status_code == 403

    v1 = mentor.post(f"/admin/api/studio/drafts/{a['id']}/publish").json()
    assert v1["id"] == 1 and v1["items"] == [a["id"]] and v1["lessons"] == 1
    t.post(f"/profiles/{pid}/chat", json={"message": "How will my career go next year?"})
    assert "FROM YOUR ASTROLOGERS" in _turn(env[-1]) and CAREER in _turn(env[-1])
    assert "FROM YOUR ASTROLOGERS" not in env[-1]["system"][0]["text"]       # the cached system prompt is unchanged
    t.post(f"/profiles/{pid}/chat", json={"message": "Will my marriage be happy with my spouse?"})
    assert CAREER not in _turn(env[-1])                                     # other topics don't get it

    v2 = owner.post(f"/admin/api/studio/drafts/{b['id']}/publish").json()
    assert v2["id"] == 2 and v2["items"] == sorted([a["id"], b["id"]])
    v3 = mentor.post("/admin/api/studio/rollback").json()                   # one step back
    assert v3["id"] == 3 and v3["items"] == [a["id"]]
    assert storage.get_draft(b["id"])["status"] == "retired" and storage.get_draft(a["id"])["status"] == "published"
    t.post(f"/profiles/{pid}/chat", json={"message": "Will my marriage be happy with my spouse soon?"})
    assert MARRIAGE not in _turn(env[-1])
    v4 = mentor.post("/admin/api/studio/rollback", json={"version": 0}).json()  # nothing published
    assert v4["items"] == [] and storage.get_draft(a["id"])["status"] == "retired"
    assert mentor.post("/admin/api/studio/rollback", json={"version": 9}).status_code == 422

    teach_view = meera.get("/admin/api/studio/teach").json()
    assert teach_view["version"]["id"] == 4 and [v["id"] for v in teach_view["versions"]] == [4, 3, 2, 1]
    log = [e["action"] for e in owner.get("/admin/api/audit").json()]
    assert log[:2] == ["rolled back teaching", "rolled back teaching"] and "published a lesson" in log


def test_retire_and_answer_cache_follows_the_version(env):
    owner = _login("admin-code")
    d = owner.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "General", "text": CAREER}).json()
    profile = {"request": {"tz_name": "Asia/Kolkata", "lat": 0, "lon": 0}, "owner": None}
    before = chat.answer_key(profile, "how will my career go in 2027")
    owner.post(f"/admin/api/studio/drafts/{d['id']}/publish")
    after = chat.answer_key(profile, "how will my career go in 2027")
    assert before != after and ":t1:" in after
    assert owner.post(f"/admin/api/studio/drafts/{d['id']}/retire").json()["items"] == []
    assert owner.post(f"/admin/api/studio/drafts/{d['id']}/retire").status_code == 409
    assert owner.get("/admin/api/audit").json()[0]["action"] == "retired a lesson"


def test_bad_drafts_are_blocked_and_only_authors_edit_drafts(env):
    owner = _login("admin-code")
    mentor, meera, ravi = _team(owner)
    bad = meera.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Remedies",
                                                       "text": "Tell them to chant the mantra 108 times daily."})
    assert bad.status_code == 422 and "japa" in bad.json()["detail"]
    d = meera.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Career & job", "text": CAREER}).json()
    assert ravi.patch(f"/admin/api/studio/drafts/{d['id']}", json={"text": MARRIAGE}).status_code == 403
    assert meera.patch(f"/admin/api/studio/drafts/{d['id']}", json={"text": "Saturn is a curse here."}).status_code == 422
    r = meera.patch(f"/admin/api/studio/drafts/{d['id']}", json={"text": CAREER + " Say why.", "topic": "General"})
    assert r.status_code == 200 and r.json()["topic"] == "General"
    mentor.post(f"/admin/api/studio/drafts/{d['id']}/publish")
    assert meera.patch(f"/admin/api/studio/drafts/{d['id']}", json={"text": MARRIAGE}).status_code == 409
    assert mentor.delete(f"/admin/api/studio/drafts/{d['id']}").status_code == 409
    e = ravi.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "General", "text": MARRIAGE}).json()
    assert meera.delete(f"/admin/api/studio/drafts/{e['id']}").status_code == 403
    assert mentor.delete(f"/admin/api/studio/drafts/{e['id']}").status_code == 200
    assert [x["id"] for x in owner.get("/admin/api/studio/drafts").json()] == [d["id"]]


def test_gold_answers_closest_first_and_playground_tries_drafts(env):
    t = _login("tester-code", "/")
    pid = t.post("/profiles", json=BODY).json()["id"]
    owner = _login("admin-code")
    golds = []
    for q, ans in (("When will I get a promotion at my job?", "Ravi ji, the promotion window opens with Jupiter."),
                   ("Should I change my job to a new company?", "Ravi ji, a change suits the Venus period."),
                   ("Is my office boss supportive of my work?", "Ravi ji, the 10th lord is friendly to the 6th.")):
        golds.append(owner.post("/admin/api/studio/drafts", json={"kind": "gold", "topic": "Career & job", "text": ans,
                                                                  "question": q}).json())
    for g in golds[:2]:
        owner.post(f"/admin/api/studio/drafts/{g['id']}/publish")
    lessons, gold = teach.pick(teach.live_items(), "When will my promotion at the job come?")
    assert lessons == [] and [g["id"] for g in gold] == [golds[0]["id"], golds[1]["id"]]

    lesson = owner.post("/admin/api/studio/drafts", json={"kind": "lesson", "topic": "Career & job", "text": CAREER}).json()
    r = owner.post("/admin/api/playground", json={"profile_id": pid, "question": "How is my career and job this year?",
        "variants": [{}, {"label": "With draft", "drafts": [lesson["id"]]}, ]})
    live, test = r.json()["results"]
    assert CAREER not in live["seen"]["teaching"] and CAREER in test["seen"]["teaching"]
    off = owner.post("/admin/api/playground", json={"profile_id": pid, "question": "How is my career and job this year?",
                                                    "variants": [{"no_teaching": True}]}).json()["results"][0]
    assert off["seen"]["teaching"] == ""
    assert storage.get_draft(lesson["id"])["status"] == "draft"             # trying a draft never publishes it
