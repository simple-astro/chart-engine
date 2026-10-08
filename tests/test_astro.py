"""Lal Kitab and match-making."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import lalkitab, matchmaking as mm

A = {"name": "A", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
B = {"name": "B", "dob": "1992-11-02", "tob": "06:10:00", "lat": 19.076, "lon": 72.8777, "tz_name": "Asia/Kolkata"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    return TestClient(app)


def test_koota_tables_are_consistent():
    n = len(mm.YONI_ORDER)
    assert all(mm.YONI_POINTS[i][j] == mm.YONI_POINTS[j][i] for i in range(n) for j in range(n))
    assert all(mm.YONI_POINTS[i][i] == 4 for i in range(n))
    for t in (mm.GANA_BY_NAKSHATRA, mm.NADI_BY_NAKSHATRA, mm.YONI_BY_NAKSHATRA):
        assert len(t) == 27
    assert set(mm.YONI_BY_NAKSHATRA) <= set(mm.YONI_ORDER)


def _fake_chart(sign, nak, deg=10.0, lagna=0, mars=0):
    g = {p: {"sign_index": 0, "sign": "Aries", "retrograde": False} for p in lalkitab.GRAHAS}
    g["Moon"] = {"sign_index": sign, "sign": mm.SIGN_LORD[sign], "degrees_in_sign": deg,
                 "nakshatra": "x", "nakshatra_index": nak, "pada": 1, "retrograde": False}
    g["Mars"] = {"sign_index": mars, "sign": "x", "retrograde": False}
    return {"grahas": g, "lagna": {"sign_index": lagna, "sign": "Aries"}, "meta": {"name": "x"}}


def test_perfect_match_scores_36_minus_nadi_when_same_person():
    c = _fake_chart(3, 8)  # same chart both sides: all kootas full except Nadi (same nadi => 0)
    r = mm.compute_match(c, c)
    got = {k["name"]: k["got"] for k in r["kootas"]}
    assert got["Nadi"] == 0 and got["Gana"] == 6 and got["Bhakoot"] == 7 and got["Yoni"] == 4
    assert r["total"] == 28 and r["max"] == 36


def test_bhakoot_and_nadi_dosha_notes():
    r = mm.compute_match(_fake_chart(0, 0), _fake_chart(5, 5))  # signs 6 apart, both Adi nadi
    assert any("Bhakoot" in n for n in r["notes"]) and any("Nadi" in n for n in r["notes"])


def test_manglik():
    assert mm.manglik(_fake_chart(0, 0, lagna=0, mars=6))["manglik"] is True   # Mars in 7th
    assert mm.manglik(_fake_chart(0, 0, lagna=0, mars=2))["manglik"] is False  # Mars in 3rd from both


def test_lal_kitab_rules():
    c = _fake_chart(0, 0)
    for p in lalkitab.GRAHAS:
        c["grahas"][p]["sign_index"] = 0
    c["grahas"]["Venus"]["sign_index"] = 1  # house 2
    c["grahas"]["Ketu"]["sign_index"] = 3   # house 4
    r = lalkitab.compute_lal_kitab(c)
    assert any("Pitru" in x["name"] for x in r["rin"]) and any("Matru" in x["name"] for x in r["rin"])
    sun = next(p for p in r["planets"] if p["planet"] == "Sun")
    assert sun["house"] == 1 and "In pakka ghar (strong)" in sun["status"] and "Exalted by house" in sun["status"]
    assert len(r["remedies"]) == 9


def test_endpoints(client):
    lk = client.post("/lal-kitab", json=A).json()
    assert len(lk["planets"]) == 9 and lk["remedies"] and "Lahiri" in lk["convention"]
    a = client.post("/profiles", json=A).json()["id"]
    b = client.post("/profiles", json=B).json()["id"]
    m = client.post("/matchmaking", json={"groom_id": a, "bride_id": b}).json()
    assert 0 <= m["total"] <= 36 and len(m["kootas"]) == 8 and m["verdict"]
    assert client.post("/matchmaking", json={"groom_id": a, "bride_id": a}).status_code == 422
    assert client.post("/matchmaking", json={"groom_id": a, "bride_id": 999}).status_code == 404


def test_chat_tools(client):
    from app import chat, storage
    a = client.post("/profiles", json=A).json()["id"]
    b = client.post("/profiles", json=B).json()["id"]
    p = storage.get(a)
    assert chat.run_tool(p, "get_lal_kitab", {})["planets"]
    assert [x["id"] for x in chat.run_tool(p, "list_profiles", {})["profiles"]] == [b]
    assert chat.run_tool(p, "match_with_profile", {"partner_id": b, "native_role": "groom"})["max"] == 36


def _chart(moon_sign, nak, pada=1, **signs):
    c = _fake_chart(moon_sign, nak, lagna=signs.pop("lagna", 0), mars=signs.pop("Mars", 0))
    c["grahas"]["Moon"]["pada"] = pada
    for p, s in signs.items():
        c["grahas"][p]["sign_index"] = s
    return c


def _dosha(r, koota):
    return next(d for d in r["doshas"] if d["koota"] == koota)


def test_bhakoot_cancelled_when_moon_signs_share_a_lord():
    r = mm.compute_match(_chart(0, 0), _chart(7, 16))  # Aries / Scorpio: 6/8, both ruled by Mars
    d = _dosha(r, "Bhakoot")
    assert d["status"] == "cancelled" and "Mars" in d["why"] and d["name"] == "Bhakoot Dosha (6/8)"
    assert r["adjusted_total"] == r["total"] + 7


def test_nadi_cancelled_for_same_sign_different_nakshatra_but_not_same_pada():
    r = mm.compute_match(_chart(1, 2), _chart(1, 3))  # Krittika / Rohini in Taurus: both Antya nadi
    assert _dosha(r, "Nadi")["status"] == "cancelled"
    same = mm.compute_match(_chart(3, 8), _chart(3, 8))
    assert _dosha(same, "Nadi")["status"] == "present" and same["adjusted_total"] == same["total"] == 28
    assert _dosha(mm.compute_match(_chart(3, 8, pada=1), _chart(3, 8, pada=3)), "Nadi")["status"] == "reduced"


def test_manglik_levels_and_exceptions():
    strong = mm.manglik(_chart(0, 0, Mars=6, Jupiter=1))  # Mars 7th from lagna, Moon and Venus
    assert strong["level"] == "strong" and strong["effective"] == "strong" and strong["hits"] == ["Lagna", "Moon", "Venus"]
    aspected = mm.manglik(_chart(0, 0, Mars=6, Jupiter=0))  # Jupiter's 7th aspect falls on Mars
    assert aspected["effective"] == "moderate" and "Jupiter aspects Mars" in aspected["exceptions"]
    own = mm.manglik(_chart(0, 0, Mars=0, Jupiter=1))  # Mars in Aries, own sign
    assert own["manglik"] and own["cancelled"] and own["effective"] == "none"


def test_manglik_match_concern_or_balanced_by_saturn():
    groom = _chart(0, 0, Mars=6, Jupiter=1, Saturn=2)
    r = mm.compute_match(groom, _chart(4, 10, Mars=2, Jupiter=1, Saturn=2))
    assert r["manglik"]["status"] == "concern" and any(c["area"] == "Mangal dosha" for c in r["clashes"])
    r = mm.compute_match(groom, _chart(4, 10, Mars=2, Jupiter=1, Saturn=6))  # bride's Saturn in her 7th
    assert r["manglik"]["status"] == "balanced"


def test_overall_verdict_and_promise_on_real_charts(client):
    a = client.post("/profiles", json=A).json()["id"]
    b = client.post("/profiles", json=B).json()["id"]
    m = client.post("/matchmaking", json={"groom_id": a, "bride_id": b}).json()
    assert m["overall"]["tier"] in mm.TIER and m["overall"]["summary"].endswith(".")
    assert m["adjusted_total"] >= m["total"]
    for side in ("groom", "bride"):
        p = m[side]["promise"]
        assert p["verdict"] in ("promised", "promised with obstacles", "not clearly promised") and p["cusp_sub_lord"]
    assert m["strengths"] or m["clashes"]
