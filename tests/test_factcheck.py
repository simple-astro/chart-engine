"""Guardrail: wrong astrological facts are caught, corrected or removed before the user sees them."""
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app import chat, factcheck as F, storage, synthesis
from app.main import app

BIRTH = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata"}
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)

GOOD = """You are in Venus mahadasha (major period) with Mercury antardasha (sub-period) until April 2029. Mercury rules your 10th house of career and your 7th house of partnerships, and it sits in your 9th house of luck.
Mercury is joined by Sun, Mars and Venus, which forms Raja yoga and Dhana yoga. Ketu in the 10th adds focus.
Mercury is combust (too close to the Sun), so recognition can come slowly.
16 Nov 2026 to 16 Jan 2027: Ketu. A restless phase.
Jan to Jun 2028: Rahu. Possible sudden changes."""


@pytest.fixture
def facts():
    c = TestClient(app).post("/chart", json=BIRTH).json()
    return F.facts_from(synthesis.build({"chart": c, "request": BIRTH}, NOW), c)


def claims(text, facts):
    return {i["claim"] for i in F.check(text, facts)}


def test_accurate_answer_passes(facts):
    assert F.check(GOOD, facts) == []


@pytest.mark.parametrize("text,claim", [
    ("Mercury sits exalted in your 9th.", "Mercury exalted"),
    ("Venus is retrograde now, so decisions are slow.", "Venus retrograde"),
    ("Your Moon isn't weak — it's in its own sign.", "Moon in own sign"),
    ("Jupiter's current aspect on your 10th house helps.", "Jupiter aspects H10"),
    ("Saturn rules your 10th house.", "Saturn rules H10"),
    ("Saturn sits in your 7th house.", "Saturn in H7"),
    ("Mercury is friendly here and aspects your career house strongly.", "Mercury aspects H10"),
    ("Venus sits in your house of marriage.", "Venus in H7"),
    ("Mercury in Virgo gives sharp analysis.", "Mercury in Virgo"),
    ("You have a strong Gaja Kesari yoga.", "Gaja Kesari"),
    ("You are currently in Sade Sati.", "Sade Sati now"),
    ("You're currently in Rahu mahadasha.", "Rahu mahadasha now"),
    ("Your Ketu antardasha (Nov 2026 – Jan 2027) brings change.", "Ketu antardasha Jan 2027"),
    ("You're in Venus-Mercury antardasha until June 2026.", "Mercury antardasha Jun 2026"),
    ("Now to June 2029: Mercury antardasha (your main influence).", "Mercury antardasha Jun 2029"),
    ("Now to Nov 2026: Mercury with Ketu pratyantar—a clearing phase.", "Ketu period Oct 2026–Nov 2026"),
    ("Nov 2026 to Jan 2027: Mercury with Venus—networking peaks.", "Venus period Nov 2026–Jan 2027"),
    ("Your Mars pratyantar from March 2027 brings energy.", "Mars pratyantar Mar 2027"),
    ("A big change came in March 1950.", "March 1950"),
    ("Your Taurus rising gives patience.", "Taurus rising"),
])
def test_wrong_facts_are_caught(facts, text, claim):
    assert claim in claims(text, facts)


@pytest.mark.parametrize("text", [
    "Your Moon is debilitated, but Neecha Bhanga cancels it.",
    "Mercury is not exalted, but it is friendly.",
    "Gaja Kesari yoga is not present in your chart.",
    "Saturn is transiting your 4th house, aspecting your 6th.",
    "Jupiter aspects your 9th and 11th.",
    "Mercury rules your career house.",
    "Saturn is transiting your 4th house and aspecting your career house.",
    "Sagittarius rising makes you optimistic.",
    "Until 16 Nov 2026: Mercury-Mercury. Good for skill.",
    "16 Nov 2026 to 16 Jan 2027: Ketu. A restless phase.",
    "16 Jan to 7 Jul 2027: Venus. A good window for raises.",
    "Mid-2027 to Jan 2028: Sun, Moon and Mars. Visibility grows.",
    "The Ketu pratyantar starts 16 Nov 2026.",
    "Mercury antardasha runs until April 2029.",
])
def test_true_or_negated_statements_pass(facts, text):
    assert F.check(text, facts) == []


def test_strip_removes_only_bad_sentences(facts):
    text = "Mercury is friendly in Leo. Venus is retrograde now. Chant on Wednesdays."
    out = F.strip(text, F.check(text, facts))
    assert out == "Mercury is friendly in Leo.  Chant on Wednesdays." or "retrograde" not in out


class FakeStream:
    def __init__(self, texts):
        self.text_stream, self.resp = texts, NS(stop_reason="end_turn", content=[NS(type="text", text="".join(texts))],
                                                 usage=None, model="claude-haiku-4-5")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.resp


def _run(monkeypatch, tmp_path, drafts):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    calls = []

    class Msgs:
        def stream(self, **kw):
            calls.append(kw)
            return FakeStream([drafts[min(len(calls), len(drafts)) - 1]])
    monkeypatch.setattr(chat, "_client", lambda: NS(messages=Msgs()))
    pid = TestClient(app).post("/profiles", json=BIRTH).json()["id"]
    return chat.chat(storage.get(pid), "How is my career?"), calls, pid


def test_wrong_draft_is_rewritten_before_the_user_sees_it(monkeypatch, tmp_path):
    r, calls, pid = _run(monkeypatch, tmp_path, ["Mercury is exalted, so career rises.",
                                                  "Mercury is friendly in Leo, so career rises steadily."])
    assert r["reply"] == "Mercury is friendly in Leo, so career rises steadily."
    assert "not exalted" in calls[1]["messages"][-1]["content"]  # the model was told exactly what was wrong
    log = storage.recent_queries(1)[0]
    assert log["factcheck"]["found"] and log["factcheck"]["revised"] and not log["factcheck"]["removed"]


def test_still_wrong_sentences_are_removed(monkeypatch, tmp_path):
    r, _, _ = _run(monkeypatch, tmp_path, ["Venus is retrograde now. Chant on Fridays.",
                                           "Venus is retrograde, sadly. Chant on Fridays."])
    assert "retrograde" not in r["reply"] and "Chant on Fridays." in r["reply"]
    assert storage.recent_queries(1)[0]["factcheck"]["removed"]


def test_clean_draft_costs_no_extra_call(monkeypatch, tmp_path):
    r, calls, _ = _run(monkeypatch, tmp_path, ["Mercury rules your 10th house."])
    assert len(calls) == 1 and r["reply"] == "Mercury rules your 10th house."
    assert storage.recent_queries(1)[0]["factcheck"] == {"found": [], "revised": False, "removed": []}


def test_cached_answer_failing_the_check_is_not_reused(monkeypatch, tmp_path):
    r, calls, pid = _run(monkeypatch, tmp_path, ["Mercury rules your 10th house."])
    key = chat.answer_key(storage.get(pid), "How is my career?")
    from datetime import date
    storage.cache_put(pid, key, chat.local_today(storage.get(pid)).isoformat(), "Mercury is exalted, a great sign.")
    again = chat.chat(storage.get(pid), "How is my career?")
    assert again["mode"] == "llm" and "exalted" not in again["reply"]


def test_chat_day_guide_uses_the_users_place_and_local_clock(monkeypatch, tmp_path):
    from datetime import date as _d, datetime as _dt
    from zoneinfo import ZoneInfo
    r, calls, pid = _run(monkeypatch, tmp_path, ["Mercury rules your 10th house."])
    p = {**storage.get(pid), "viewer": {"lat": 49.8951, "lon": -97.1384, "tz_name": "America/Winnipeg", "name": "Winnipeg"}}
    g = chat.day_guide(p, _d(2026, 10, 10))
    assert g["place"] == "Winnipeg" and g["time_zone"] == "America/Winnipeg" and g["weekday"] == "Saturday"
    assert g["local_times"]["sunrise"].endswith("AM") and "–" in g["local_times"]["rahu_kalam_avoid"]
    assert g["for_you"]["wear"] and isinstance(g["for_you"]["colours_to_avoid"], list) and g["for_you"]["do"]
    assert chat.local_today(p) == _dt.now(ZoneInfo("America/Winnipeg")).date()
    from app import synthesis
    s = synthesis.build(p)
    assert s["user_location"] == {"place": "Winnipeg", "time_zone": "America/Winnipeg"}
    assert s["today"] == chat.local_today(p).isoformat()
    assert chat.where(storage.get(pid))["place"]  # without a chosen place: the birthplace
