"""KP prediction engine: promise, lord judgement, windows, routing, and the chat/guard wiring."""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import factcheck as F, synthesis
from app.main import app
from core import kp_predict as K

BIRTH = {"name": "Sukh", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629, "lon": 76.7884, "tz_name": "Asia/Kolkata"}
START = date(2026, 10, 8)


@pytest.fixture(scope="module")
def chart():
    return TestClient(app).post("/chart", json=BIRTH).json()


def test_career_uses_confirmed_houses_and_promise(chart):
    r = K.predict(chart, "career", START)
    assert r["houses_for"] == [2, 6, 10, 11] and r["houses_against"] == [5, 9]
    p = r["promise"]
    assert p["cusp_sub_lord"] == "Mercury" and p["verdict"] == "promised" and 10 in p["signifies"]


def test_lord_judgement_three_levels(chart):
    good, bad = {2, 6, 10, 11}, {5, 9}
    sun = K.judge_lord(chart, "Sun", good, bad)
    assert set(sun["levels"]) == {"planet", "nakshatra", "sub"} and sun["levels"]["sub"]["lord"] == "Venus"
    assert sun["verdict"] == "leans good"  # sub lord Venus signifies 6, 11 against 9
    assert K.judge_lord(chart, "Jupiter", good, bad)["verdict"] in ("against", "blocks")


def test_book_worked_example_scoring():
    """Taneja's marriage example (H1): sub lord strongest, then nakshatra, then planet."""
    good, bad = {2, 7, 11}, {1, 6, 10}
    v = lambda s: max(-2, min(2, len(s & good) - len(s & bad)))
    score = lambda p, n, s: K.WEIGHT_LEVEL["planet"] * v(p) + K.WEIGHT_LEVEL["nakshatra"] * v(n) + K.WEIGHT_LEVEL["sub"] * v(s)
    assert score({4, 6, 8, 9, 11}, {2, 7}, {4, 8, 11}) >= 3            # Ketu: strong for marriage
    assert 1 <= score({1, 2, 7}, {3, 5, 10}, {1, 2, 3, 4, 8, 11, 12}) < 3  # Saturn: possible but weak
    assert score({1, 3, 12}, {1, 2, 3, 4, 8, 11, 12}, {4, 6, 9}) <= -1    # Jupiter: not possible


def test_nodes_act_as_agents(chart):
    # Ketu alone in Virgo: its own house plus its sign lord Mercury's houses
    assert K.own_houses(chart, "Ketu") >= set(chart["significators"]["by_planet"]["Mercury"]["owned"])


def test_required_significator_and_dasa_gate(chart):
    r = K.predict(chart, "foreign", START)  # needs a separative planet among the DBA lords
    for w in r["windows"]:
        if not any(l in K.SEPARATIVES for l in (w["maha"], w["antar"], w["praty"])) and \
                not any(n.startswith("Significator") for n in w["transit"]):
            assert w["verdict"] in ("mixed", "challenging")


def test_risk_topics_are_labelled(chart):
    r = K.predict(chart, "illness", START)
    assert r["kind"] == "risk" and "RISK reading" in K.brief(r)


def test_windows_cover_the_horizon(chart):
    r = K.predict(chart, "career", START, months=24)
    ws = r["windows"]
    assert ws[0]["starts"] <= START.isoformat() < ws[0]["ends"]
    assert all(a["ends"] == b["starts"] for a, b in zip(ws, ws[1:]))
    assert {w["verdict"] for w in ws} <= {"strong", "favourable", "mixed", "challenging"}
    by = {w["praty"]: w for w in ws}
    assert by["Venus"]["score"] > by["Mars"]["score"]  # supporting pratyantar beats a blocking one
    assert all(len(w["reasons"]) == 3 for w in ws)


def test_topic_routing():
    assert K.topics_for("When will I get a promotion at my job?") == ["career"]
    assert K.topics_for("Will I win the court case?") == ["litigation_win"]
    assert K.topics_for("Should I sell my house this year?")[0] == "property_sale" or "property_sale" in K.topics_for("Should I sell my house this year?")
    assert K.topics_for("Will I settle abroad after marriage?") == ["marriage", "foreign"]
    assert K.topics_for("What does my Moon mean?") == []


def test_brief_is_compact_and_complete(chart):
    b = K.brief(K.predict(chart, "career", START))
    assert "promised" in b and "2026-06-23 to 2026-11-16" in b and b.count("\n- ") >= 7
    assert len(b) < 3500


def test_unknown_topic(chart):
    with pytest.raises(ValueError):
        K.predict(chart, "lottery", START)


def test_guard_flags_a_window_rated_opposite(chart):
    kp = {"career": K.predict(chart, "career", START)}
    facts = F.facts_from(synthesis.build({"chart": chart, "request": BIRTH}, datetime(2026, 10, 8, tzinfo=timezone.utc)),
                         chart, kp=kp)
    strong = next(w for w in kp["career"]["windows"] if w["verdict"] == "strong")
    s, e = date.fromisoformat(strong["starts"]), date.fromisoformat(strong["ends"])
    bad = f"{s:%d %b %Y} to {e:%d %b %Y} is a difficult time for your career."
    good = f"{s:%d %b %Y} to {e:%d %b %Y} is a strong time for your career."
    assert any("called difficult" in i["claim"] for i in F.check(bad, facts))
    assert F.check(good, facts) == []


def test_chat_gets_brief_for_topic_questions_only(chart):
    from app import chat
    prof = {"chart": chart, "request": BIRTH, "id": 1}
    assert "NADI PREDICTION — Job, promotion and career" in chat.kp_context(prof, "How is my career next year?")
    assert chat.kp_context(prof, "What does my Moon mean?") == ""


def test_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=BIRTH).json()["id"]
    r = c.get(f"/profiles/{pid}/kp/marriage?months=12").json()
    assert r["topic"] == "marriage" and r["windows"]
    assert c.get(f"/profiles/{pid}/kp/lottery").status_code == 422


def test_risk_needs_a_real_combination(chart):
    # illness needs 1 and 6 together; a level with only 8 and 12 (e.g. the Moon here) does not count
    rule = K.RISK_RULES["illness"]
    assert not K._combo({8, 12}, {1, 6, 8, 12}, rule) and K._combo({1, 6}, {1, 6, 8, 12}, rule)
    # litigation: any two of 6, 8, 12, but a single one alone is harmless (book's examples)
    assert K._combo({8, 12}, {6, 8, 12}, {}) and not K._combo({6, 10, 11}, {6, 8, 12}, {})
    r = K.predict(chart, "illness", START)
    assert all(w["verdict"] in ("mixed", "challenging") for w in r["windows"])


def test_accident_requires_rahu_or_ketu(chart):
    for w in K.predict(chart, "accident", START)["windows"]:
        if w["verdict"] in ("strong", "favourable"):
            assert any(n.startswith("Significator") for n in w["transit"])


def test_bhava_chalit_matches_the_book_example():
    """Taneja's illustration H1 (7 June 1950, 22:30, Delhi): every planet's houses by position and lordship
    in the Nirayana Bhava Chalit, including Rahu/Ketu as agents, exactly as printed in the book."""
    c = TestClient(app).post("/chart", json={"dob": "1950-06-07", "tob": "22:30:00", "lat": 28.6667,
                                             "lon": 77.2167, "tz_name": "Asia/Kolkata"}).json()
    book = {"Sun": {5, 8}, "Moon": {2, 7}, "Mars": {4, 8, 11}, "Mercury": {4, 6, 9}, "Jupiter": {1, 3, 12},
            "Saturn": {1, 2, 7}, "Venus": {3, 5, 10}, "Rahu": {1, 2, 3, 4, 8, 11, 12}, "Ketu": {4, 6, 8, 9, 11}}
    assert {p: K.own_houses(c, p) for p in book} == book
    cusp1 = c["houses"][0]["longitude"]
    assert abs(cusp1 - (270 + 11 + 24 / 60)) < 0.25  # Capricorn 11°24′ in the book


def test_event_days_follow_the_transit_rules(chart):
    r = K.event_days(chart, "career", START, 180, "Asia/Kolkata")
    assert r["significators"] and r["days"]
    sig = set(r["significators"])
    for d in r["days"]:
        assert d["window"] in ("strong", "favourable") and d["hits"]
        assert any(any(f in h for f in K.FAST) for h in d["hits"])  # a fast planet fixes the day
    dates = [date.fromisoformat(d["date"]) for d in r["days"]]
    assert all((b - a).days > 2 for a, b in zip(dates, dates[1:]))  # one day per cluster


def test_event_days_endpoint_and_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=BIRTH).json()["id"]
    r = c.get(f"/profiles/{pid}/kp/career/days?start=2026-10-08&days=60").json()
    assert r["days_checked"] == 60 and r["topic"] == "career"
    assert c.get(f"/profiles/{pid}/kp/career/days?start=oops").status_code == 422
    from app import chat, storage
    out = chat.run_tool(storage.get(pid), "get_event_days", {"topic": "career", "start": "2026-10-08", "days": 30})
    assert out["days_checked"] == 30
