"""State of mind: mood logs saved with the moment's astrology, replies, patterns, privacy and Astropositivism's consent."""
import pytest
from fastapi.testclient import TestClient

from app import mood, storage, synthesis
from app.main import app
from tests.test_admin import BODY, _tester, gated  # noqa: F401  (fixture)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.delenv("TESTER_ACCESS_CODES", raising=False)
    return TestClient(app)


def _pid(c):
    return c.post("/profiles", json=BODY).json()["id"]


def test_log_saves_the_moments_astrology_and_replies(client):
    pid = _pid(client)
    r = client.post(f"/profiles/{pid}/mood", json={"valence": -2, "feelings": ["Anxious", "Stressed"],
                                                   "causes": ["Work"], "note": "Big meeting"})
    assert r.status_code == 200, r.text
    log, rep = r.json()["log"], r.json()["reply"]
    s = log["snapshot"]
    assert {"date", "time", "tara", "chandra_house", "moon_house", "rating", "hora", "rahu_kaal", "maha"} <= set(s)
    assert not any(k.startswith("_") for k in s)  # reply helpers are not shown or stored for the app
    assert rep["headline"] == "Unpleasant" and rep["sky"] and rep["timing"]
    assert rep["do"]["planet"] == "Moon" and "breathing" in rep["do"]["text"]  # anxious -> calm the Moon
    assert rep["area"] == "career" and "anxious" in rep["ask"] and "care" not in rep
    got = client.get(f"/profiles/{pid}/mood").json()
    assert [x["id"] for x in got["logs"]] == [log["id"]] and got["share"] is False
    assert "Work" in got["options"]["causes"] and "Amazed" in got["options"]["feelings"]["pleasant"]


def test_pleasant_log_points_to_the_best_time_and_giving(client):
    pid = _pid(client)
    rep = client.post(f"/profiles/{pid}/mood", json={"valence": 3, "feelings": ["Grateful"]}).json()["reply"]
    assert rep["headline"] == "Very pleasant" and "giving" in rep["do"]["text"]


def test_unknown_words_and_out_of_range_are_rejected(client):
    pid = _pid(client)
    assert client.post(f"/profiles/{pid}/mood", json={"valence": 5}).status_code == 422
    assert client.post(f"/profiles/{pid}/mood", json={"valence": 0, "feelings": ["Hungry"]}).status_code == 422
    assert client.post(f"/profiles/{pid}/mood", json={"valence": 0, "causes": ["Aliens"]}).status_code == 422


def test_care_message_for_worrying_words_or_three_hard_days():
    assert mood.care_needed(-1, "I feel hopeless", [])
    assert not mood.care_needed(-2, None, [{"local_date": "2026-10-10", "valence": -2}])
    days = [{"local_date": d, "valence": -3} for d in ("2026-10-08", "2026-10-09", "2026-10-10")]
    assert mood.care_needed(-2, None, days)
    assert not mood.care_needed(1, None, days)


def test_care_reply_lists_helplines(client):
    pid = _pid(client)
    rep = client.post(f"/profiles/{pid}/mood", json={"valence": -3, "note": "no reason to live"}).json()["reply"]
    assert "14416" in str(rep["care"]["helplines"]) and "988" in str(rep["care"]["helplines"])


def _log(v, **snap):
    base = {"tara": "Sampat", "chandra_house": 3, "chandra_score": 1, "moon_house": 5, "weekday": "Monday",
            "rating": "good", "rahu_kaal": False}
    return {"valence": v, "causes": [], "snapshot": {**base, **snap}}


def test_patterns_wait_for_enough_logs_and_are_honest_about_chance():
    assert mood.patterns([_log(1)] * 4) == {"ready": False, "logs": 4, "needed": 6, "found": []}
    logs = [_log(2) for _ in range(10)] + [_log(-2, tara="Vipat", rating="avoid") for _ in range(6)]
    p = mood.patterns(logs)
    assert p["ready"] and p["logs"] == 16
    vipat = next(x for x in p["found"] if "Vipat" in x["label"])
    assert vipat["difference"] < 0 and vipat["logs"] == 6 and vipat["strength"] == "clear"
    assert "lower than usual (6 logs)" in vipat["text"]
    assert "better" in p["rating_check"]["text"]
    few = mood.patterns([_log(1) for _ in range(10)] + [_log(0, weekday="Friday") for _ in range(3)])
    assert all(x["strength"] == "possible" and "chance" in x["text"] for x in few["found"])


def test_logs_are_private_to_their_owner(gated):
    a, b = _tester(), _tester()
    pid = a.post("/profiles", json=BODY).json()["id"]
    assert a.post(f"/profiles/{pid}/mood", json={"valence": 1}).status_code == 200
    # b signs in with the same code but is a different person (own cookie -> own owner id)
    assert b.get(f"/profiles/{pid}/mood").status_code == 404
    assert b.post(f"/profiles/{pid}/mood", json={"valence": 1}).status_code == 404
    assert b.delete(f"/profiles/{pid}/mood").status_code == 404


def test_sukh_sees_the_mood_log_only_with_consent(client):
    pid = _pid(client)
    client.post(f"/profiles/{pid}/mood", json={"valence": -1, "feelings": ["Worried"], "causes": ["Money"]})
    prof = storage.get(pid)
    assert "state_of_mind" not in synthesis.build(prof)
    assert client.put(f"/profiles/{pid}/mood/share", json={"share": True}).json() == {"share": True}
    mind = synthesis.build(prof)["state_of_mind"]
    assert mind["recent"][0]["feeling"] == "Slightly unpleasant: Worried" and mind["recent"][0]["about"] == ["Money"]
    assert "never blame the planets" in mind["rule"]
    client.put(f"/profiles/{pid}/mood/share", json={"share": False})
    assert "state_of_mind" not in synthesis.build(prof)


def test_delete_one_all_and_with_the_profile(client):
    pid = _pid(client)
    ids = [client.post(f"/profiles/{pid}/mood", json={"valence": v}).json()["log"]["id"] for v in (1, 2, 3)]
    assert client.delete(f"/profiles/{pid}/mood/{ids[0]}").json() == {"deleted": ids[0]}
    assert client.delete(f"/profiles/{pid}/mood/{ids[0]}").status_code == 404
    assert client.delete(f"/profiles/{pid}/mood").json() == {"deleted": 2}
    client.post(f"/profiles/{pid}/mood", json={"valence": 1})
    client.put(f"/profiles/{pid}/mood/share", json={"share": True})
    client.delete(f"/profiles/{pid}")
    assert storage.mood_list(pid) == [] and not storage.mood_shared(pid)


def test_every_difficult_feeling_has_a_calming_habit():
    from app import mood
    assert set(mood.FEELING_PLANET.values()) <= set(mood.CALM)
    assert {"Homesick", "Restless", "Stuck", "Confused"} <= set(mood.FEELINGS["unpleasant"])
    assert set(mood.CAUSE_AREA) <= set(mood.CAUSES) and "Visa and immigration" in mood.CAUSES
    for group in mood.FEELINGS.values():
        assert group == sorted(group) and len(group) == len(set(group))
    assert mood.CAUSES == sorted(mood.CAUSES)
