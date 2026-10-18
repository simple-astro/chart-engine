"""👍/👎 on answers (feeds Studio Review), the wider topic list, and the honest refill message."""
from fastapi.testclient import TestClient

from app import review, storage, usage
from app.main import app

BODY = {"name": "T", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.61, "lon": 77.2, "tz_name": "Asia/Kolkata"}


def test_rating_an_answer_puts_a_thumbs_down_near_the_top_of_review(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=BODY).json()["id"]
    other = c.post("/profiles", json=BODY).json()["id"]
    uid = storage.log_usage(pid, "llm", "When will I marry?", answer="In your Venus period.", model="m")
    assert c.post(f"/profiles/{other}/answers/{uid}/rating", json={"rating": -1}).status_code == 404  # not that chart's
    assert c.post(f"/profiles/{pid}/answers/{uid}/rating", json={"rating": -1, "reason": "Facts look wrong"}).json()["ok"]
    q = review.queue(storage.review_candidates())
    assert q[0]["id"] == uid and q[0]["reason"] == "down" and "Facts look wrong" in q[0]["reason_text"]
    assert storage.rating_counts("2000-01-01") == {"up": 0, "down": 1}


def test_common_questions_no_longer_fall_into_other():
    for q, t in [("Give me an overview of my chart", "My chart overall"), ("meri shaadi kab hogi", "Marriage & love"),
                 ("How is my mother's health?", "Family"), ("Who are you and what can you help me with?", "About the app"),
                 ("I feel sad these days", "Mind & mood"), ("videsh jaane ka yog hai?", "Abroad & visa")]:
        assert t in usage.topics([q]), q
