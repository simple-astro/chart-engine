"""The style checks next to the fact check: stock phrases, answers that never name the person's own placements,
and answers with nothing to do. In code, so they cost nothing unless one fires (then the same single rewrite)."""
import pytest
from fastapi.testclient import TestClient

from app import chat, storage
from app import factcheck as F
from app.main import app

BODY = {"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
LONG_VAGUE = ("Asha ji, this is a time of growth and change for you. Good things are coming and your patience will be "
              "rewarded. The months ahead bring new energy, new people and new chances. Stay hopeful and open, because "
              "what is meant for you will find you. Many people feel this way at this stage of life, and it passes. "
              "You have more strength than you know.")
GOOD = ("Asha ji, your Moon's nakshatra favours steady, patient effort at work, so a rise comes slowly. Do: keep a "
        "fixed routine and help an elder on Saturdays. Don't: switch jobs on impulse.")


def kinds(text):
    return [s["kind"] for s in F.style_check(text)]


def test_style_check():
    assert kinds("The cosmos is asking you to wait. Saturn in your 10th asks for patience; try a Saturday routine.") == ["generic"]
    assert kinds("The universe has a plan for you.") == ["generic"]
    assert set(kinds(LONG_VAGUE)) == {"specific", "actionable"}
    assert kinds(GOOD) == []
    assert kinds("Thank you, Asha ji.") == []                  # short replies are left alone
    note = F.correction_note([], 300, F.style_check("The stars say yes. " + LONG_VAGUE))
    assert "stock phrase" in note and "actual placements" in note and "Do / Don't" in note
    assert "contradicts" not in note


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    pid = TestClient(app).post("/profiles", json=BODY).json()["id"]
    return storage.get(pid)


def _guard(profile, text, monkeypatch, fixed):
    calls = []

    def revise(profile, history, message, draft, note, model=None):
        calls.append(note)
        return fixed, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    monkeypatch.setattr(chat, "revise", revise)
    out = [e for e in chat.guard(profile, [], "How is my career?", text, []) if e["type"] == "checked"][0]
    return out, calls


def test_guard_rewrites_for_style_and_records_it(profile, monkeypatch):
    out, calls = _guard(profile, "The cosmos is asking you to wait. " + LONG_VAGUE, monkeypatch, GOOD)
    assert len(calls) == 1 and "stock phrase" in calls[0]
    assert out["text"] == GOOD and out["report"]["revised"] and out["report"]["found"] == []
    assert len(out["report"]["style"]) == 2 and out["report"]["style_left"] == []   # stock phrase + no placements


def test_guard_leaves_a_clean_answer_alone(profile, monkeypatch):
    out, calls = _guard(profile, GOOD, monkeypatch, "unused")
    assert calls == [] and out["text"] == GOOD and out["report"]["style"] == []


def test_style_left_after_the_rewrite_is_logged_not_stripped(profile, monkeypatch):
    out, _ = _guard(profile, "The universe has a plan. " + LONG_VAGUE, monkeypatch, LONG_VAGUE)
    assert out["text"] == LONG_VAGUE and set(out["report"]["style_left"]) == {
        "names none of their actual placements (planet, house, sign, nakshatra or dasha)",
        "gives nothing concrete to do and no upaya"}
