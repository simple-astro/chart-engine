"""The Life Book (app/lifebook.py): answers first, written in the background, reviewed and approved by the
astrologer before the person can read it."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import chat, lifebook, storage
from app.main import app

SUKH = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884,
        "tz_name": "Asia/Kolkata", "ayanamsha": "krishnamurti"}
ANSWERS = {"focus": ["career", "marriage", "nonsense"], "stage": {"work": "business", "relationship": "married"},
           "questions": ["When is my best time for business growth?"],
           "events": [{"kind": "married", "year": 2016, "month": 2}, {"kind": "job", "year": 2010}],
           "ratings": {"career": 3, "money": 9}, "prefs": {"remedies": "habits"}, "consent": True}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    asked = []

    def answer_once(profile, message, model, test=None, explain=False):
        asked.append(message)
        return {"text": "Sukh ji, your Mercury antardasha runs to April 2029."}
    monkeypatch.setattr(chat, "answer_once", answer_once)
    monkeypatch.setattr(lifebook, "start", lifebook.run)  # write it now, not in a thread
    c = TestClient(app)
    c.asked = asked
    return c


def test_the_rules_chapters():
    from app.routes import chart as compute
    from app.schemas import ChartRequest
    p = {"id": None, "name": "Sukh", "request": SUKH, "chart": compute(ChartRequest(**SUKH))}
    b = lifebook.build(p, {"focus": ["career"], "stage": {"relationship": "married"}, "ratings": {"peace": 4}}, date(2026, 10, 23))
    keys = [c["key"] for c in b["chapters"]]
    assert keys == ["glance", "strengths", "lords", "watch", "windows", "year", "balance", "method"]  # no dates given: no fit chapter
    lords = next(c for c in b["chapters"] if c["key"] == "lords")["blocks"][0]["items"]
    assert len(lords) == 12 and lords[1]["title"] == "2nd lord Saturn in your 12th house"
    watch = next(c for c in b["chapters"] if c["key"] == "watch")["blocks"][0]["items"]
    assert watch[0]["sub"].startswith("A habit that helps: Be fair to workers")
    rows = next(c for c in b["chapters"] if c["key"] == "balance")["blocks"][0]["rows"]
    assert rows[-1] == ["Peace of mind", "You: 4/5 · Chart now: Well supported (your 4th lord)"]


def test_answers_review_then_ready(client):
    pid = client.post("/profiles", json=SUKH).json()["id"]
    assert client.get(f"/profiles/{pid}/lifebook").json() == {"status": None}
    r = client.post(f"/profiles/{pid}/lifebook", json=ANSWERS).json()
    assert r["status"] == "writing"
    mine = client.get(f"/profiles/{pid}/lifebook").json()
    assert mine["status"] == "review" and "book" not in mine                       # hidden until approved
    assert "I am running a business, married" in client.asked[0]                   # the AI knows their life
    assert {e["kind"] for e in storage.event_list(pid)} == {"married", "job"}       # dates saved as life events
    assert mine["answers"]["focus"] == ["career", "marriage"] and mine["answers"]["ratings"] == {"career": 3, "money": 5}
    assert client.post(f"/profiles/{pid}/lifebook", json=ANSWERS).status_code == 409   # one at a time

    bid = mine["id"]
    rv = client.get(f"/admin/api/lifebooks/{bid}").json()
    titles = [c["title"] for c in rv["book"]["chapters"]]
    assert titles[1] == "Your questions answered" and "How your chart fits your life" in titles
    qa = rv["book"]["chapters"][1]["blocks"][0]["items"][0]
    assert qa["a"].startswith("Sukh, your Mercury")                                 # no 'ji', like the chat
    client.put(f"/admin/api/lifebooks/{bid}", json={"notes": "Start the expansion in early 2027.", "status": "ready"})
    done = client.get(f"/profiles/{pid}/lifebook").json()
    assert done["status"] == "ready" and done["book"]["chapters"][-2]["title"] == "Notes from your astrologer"
    assert client.get("/admin/api/lifebooks").json()["books"][0]["status"] == "ready"
    pdf = client.get(f"/profiles/{pid}/lifebook.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content[:5] == b"%PDF-"
    assert 'filename="sukh-life-book.pdf"' in pdf.headers["content-disposition"]


def test_no_pdf_before_the_book(client):
    pid = client.post("/profiles", json=SUKH).json()["id"]
    assert client.get(f"/profiles/{pid}/lifebook.pdf").status_code == 404


def test_consent_is_needed(client):
    pid = client.post("/profiles", json=SUKH).json()["id"]
    assert client.post(f"/profiles/{pid}/lifebook", json={**ANSWERS, "consent": False}).status_code == 422
