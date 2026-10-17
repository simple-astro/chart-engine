"""Jamakkol Prashna: the calculation checked against a worked chart from another Jamakkol app (jama planets) and
the Tamil teaching examples (Udayam, Arudam, Kavippu), and the rule-based reading."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import jamakkol as J

WPG = (49.8951, -97.1384, "America/Winnipeg")
KOVAI = (11.0168, 76.9558, "Asia/Kolkata")


def at(y, mo, d, h, mi, s=0, tz="America/Winnipeg"):
    return datetime(y, mo, d, h, mi, s, tzinfo=ZoneInfo(tz))


def test_matches_a_live_calculator_chart():
    # jamakkolprasannam.com, 18 Oct 2026 00:15:19 IST (sunrise 06:00, sunset 17:52): night, Saturday's jama day
    t = at(2026, 10, 18, 0, 15, 19, tz="Asia/Kolkata")
    j = J.jama_positions(t, "Asia/Kolkata")
    got = {p: (x["sign"], round(x["lon"])) for p, x in j["planets"].items()}
    assert got == {"Sun": ("Taurus", 37), "Mars": ("Pisces", 352), "Jupiter": ("Aquarius", 307),
                   "Mercury": ("Sagittarius", 262), "Venus": ("Scorpio", 217), "Saturn": ("Virgo", 172),
                   "Moon": ("Leo", 127), "Paambu": ("Gemini", 82)}
    c = J.cast(t, 13.0827, 80.2707, "Asia/Kolkata")
    assert c["period"] == "night" and c["udayam"]["sign"] == "Aries" and 8.5 < c["udayam"]["deg"] < 11
    assert (c["arudam"]["sign"], round(c["arudam"]["deg"], 1)) == ("Cancer", 1.9)      # shown as 1°54'
    assert c["kavippu"]["sign"] == "Aquarius"
    # another app's chart, Saturday 17 Oct 11:35: the same jama degrees
    j = J.jama_positions(at(2026, 10, 17, 11, 35, 52), "America/Winnipeg")
    assert (j["weekday"], j["number"], j["ruler"]) == ("Saturday", 4, "Jupiter")
    assert {p: round(x["lon"]) for p, x in j["planets"].items()} == {
        "Jupiter": 327, "Mercury": 282, "Venus": 237, "Saturn": 192, "Moon": 147, "Paambu": 102, "Sun": 57, "Mars": 12}


def test_jama_day_runs_six_to_six():
    j = J.jama_positions(at(2026, 10, 18, 5, 0), "America/Winnipeg")         # Sunday 5 am: still Saturday's
    assert j["weekday"] == "Saturday" and j["number"] == 16
    j = J.jama_positions(at(2026, 10, 18, 6, 0), "America/Winnipeg")         # Sunday 6 am: the Sun at Pisces' end
    assert j["ruler"] == "Sun" and j["planets"]["Sun"]["lon"] == 0.0
    assert J.jama_positions(at(2026, 10, 18, 18, 10), "America/Winnipeg")["ruler"] == "Sun"   # night repeats


def test_arudam_from_the_minute_hand():
    for (h, m), sign in (((7, 23), "Leo"), ((3, 19), "Cancer"), ((5, 57), "Pisces"), ((11, 35), "Scorpio")):
        assert J.cast(at(2026, 10, 17, h, m), *WPG)["arudam"]["sign"] == sign


def test_kavippu_and_udayam_match_the_tamil_examples():
    for u, a, sun, want in ((3, 9, 6, 7), (5, 7, 9, 0), (2, 0, 1, 2)):
        assert (u + (J.VEEDHI[sun] - a) % 12) % 12 == want
    c = J.cast(at(2026, 8, 21, 14, 43, tz="Asia/Kolkata"), *KOVAI)              # Avani 5, Kovai, 2:43 pm
    assert c["period"] == "day" and c["udayam"]["sign"] == "Aries" and c["arudam"]["sign"] == "Sagittarius"


def test_udayam_starts_at_the_sun_and_runs_the_zodiac_by_sunset():
    c = J.cast(at(2026, 10, 17, 12, 0), *WPG)
    start = datetime.fromisoformat(c["period_start"])
    first = J.cast(start, *WPG)
    sun = first["transit"]["Sun"]["lon"]
    assert abs((first["udayam"]["lon"] - sun + 180) % 360 - 180) < 0.1
    night = J.cast(datetime.fromisoformat(c["period_end"]), *WPG)                # sunset: back at the Sun
    assert night["period"] == "night"
    assert abs((night["udayam"]["lon"] - night["transit"]["Sun"]["lon"] + 180) % 360 - 180) < 0.2


def test_reading_rules():
    c = J.cast(at(2026, 10, 17, 11, 35, 52), *WPG)
    r = J.read(c, "career")
    assert r["verdict"] in ("yes", "likely", "mixed", "no") and r["label"]
    assert r["arudam_house"] == (c["arudam"]["sign_index"] - c["udayam"]["sign_index"]) % 12 + 1
    # the significator with the Kavippu blocks the matter, whatever else is good
    k = c["kavippu"]["sign_index"]
    c2 = {**c, "jama": {**c["jama"], "planets": {**c["jama"]["planets"], "Saturn": {"lon": k * 30 + 5, "sign_index": k,
                                                                                         "sign": "x"}}}}
    blocked = J.read(c2, "career")
    assert blocked["verdict"] == "no" and blocked["label"] == "Not favourable now" and blocked["obstacles"]
    with pytest.raises(ValueError):
        J.read(c, "death")
    text = " ".join(str(v) for v in J.read(c, "general").values()).lower()
    assert not re.search(r"\b(death|die|black magic|spirits?|poison)\b", text)


def test_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    assert [k["kind"] for k in c.get("/jamakkol/kinds").json()][:2] == ["career", "business"]
    r = c.post("/jamakkol", json={"kind": "marriage", "lat": 49.9, "lon": -97.1, "tz_name": "America/Winnipeg",
                                  "asked_at": "2026-10-17T11:35:52-05:00"})
    assert r.status_code == 200 and r.json()["reading"]["question"]["title"] == "Marriage or a match"
    assert c.post("/jamakkol", json={"kind": "marriage", "lat": 49.9, "lon": -97.1, "tz_name": "Nowhere/X"}).status_code == 422
    assert c.post("/jamakkol", json={"kind": "nope", "lat": 49.9, "lon": -97.1, "tz_name": "UTC"}).status_code == 422


def test_sky_planets_with_the_kavippu_count():
    c = J.cast(at(2026, 10, 17, 11, 35, 52), *WPG)
    k = c["kavippu"]["sign_index"]
    sky = {**c["transit"], "Saturn": {**c["transit"]["Saturn"], "sign_index": k}}
    jama = {p: {**x, "sign_index": (k + 1) % 12} for p, x in c["jama"]["planets"].items()}   # no jama planet there
    r = J.read({**c, "transit": sky, "jama": {**c["jama"], "planets": jama}}, "career")
    assert "Saturn" in r["in_kavippu"] and r["verdict"] == "no"


def test_book_rules_and_the_working():
    r = J.jamakkol("career", at(2026, 10, 17, 11, 35, 52), *WPG)
    g = r["reading"]
    assert g["confirm"][0].startswith("The 10th lord ") and "from the Udayam" in g["confirm"][0]
    assert g["kavippu_notes"][0].startswith(f"The Kavippu is in house {g['kavippu_house']}")
    assert all(p.split(" ")[0] in g["in_kavippu"] for p in g["kavippu_notes"][1:])
    assert any("head first" in x for x in g["for"])                      # Jupiter and Rahu in the Udayam
    assert any(x.startswith("Jupiter is exalted") for x in g["strengths"])
    k = r["kavippu"]
    assert (k["tamil_month"], k["veedhi"]) == ("Aippasi", "Taurus")
    assert (r["udayam"]["sign_index"] + k["count"] - 1) % 12 == k["sign_index"]
    tl = r["jama"]["timeline"]
    assert len(tl) == 16 and tl[0] == {"n": 1, "ruler": "Saturn", "start": "06:00", "end": "07:30"}
    assert tl[3]["ruler"] == "Jupiter" and tl[8]["ruler"] == "Saturn"     # jamam 4 and night's first


def test_maandi_matches_the_calculator():
    # jamakkolprasannam.com (Thiruvarur): Sunday day 12:00 Pisces 6°40', Sunday night 23:00 Gemini 1°07',
    # Wednesday night 23:00 Virgo 10°06', Saturday day 12:00 Libra 18°37'; it uses Lahiri, we use KP (~0.1° apart)
    TVR = (10.7661, 79.6384, "Asia/Kolkata")
    for (d, h), want in ((("2026-10-18", 12), 336.67), (("2026-10-18", 23), 61.12), (("2026-10-21", 23), 160.1),
                         (("2026-10-24", 12), 198.62), (("2026-10-18", 0), 84.17)):
        y, mo, da = map(int, d.split("-"))
        got = J.cast(at(y, mo, da, h, 15 if h == 0 else 0, 19 if h == 0 else 0, tz="Asia/Kolkata"), *TVR)["maandi"]["lon"]
        assert abs((got - want + 180) % 360 - 180) < 0.2, (d, h, got, want)


def test_lords_and_double_confirmation_are_information_only():
    c = J.cast(at(2026, 10, 17, 11, 35, 52), *WPG)
    g = J.read(c, "career")
    assert g["lords"]["arudam_lord"] == "Mars" and 0 <= g["lords"]["kavippu_power"] <= 4
    assert "against Kavippu lord" in g["lords"]["text"]
    assert all(p in J.JAMA for p in g["doubled"])


def test_ask_once_and_did_it_happen(tmp_path, monkeypatch):
    import sqlite3
    from datetime import timedelta
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json={"name": "Asha", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139,
                                    "lon": 77.209, "tz_name": "Asia/Kolkata"}).json()["id"]
    body = {"kind": "career", "question": "Will I get the bank job?", "lat": 49.9, "lon": -97.1, "tz_name": "America/Winnipeg"}
    first = c.post(f"/profiles/{pid}/jamakkol", json=body)
    assert first.status_code == 200 and first.json()["ask"]["due"] is False
    ask = first.json()["ask"]
    again = c.post(f"/profiles/{pid}/jamakkol", json=body)
    assert again.status_code == 409 and again.json()["detail"]["ask"]["id"] == ask["id"]
    assert c.post(f"/profiles/{pid}/jamakkol", json={**body, "again": True}).status_code == 200
    assert c.post(f"/profiles/{pid}/jamakkol", json={**body, "kind": "money"}).status_code == 200
    seen = c.get(f"/profiles/{pid}/jamakkol/{ask['id']}").json()                # the same chart again
    assert seen["udayam"] == first.json()["udayam"] and seen["reading"]["label"] == ask["label"]
    # 90 days on: the question is due for "did it happen?"
    con = sqlite3.connect(tmp_path / "p.db")
    old = (datetime.fromisoformat(ask["asked_at"]) - timedelta(days=90)).isoformat()
    con.execute("UPDATE jamakkol_asks SET asked_at = ? WHERE id = ?", (old, ask["id"])); con.commit()
    due = next(a for a in c.get(f"/profiles/{pid}/jamakkol").json() if a["id"] == ask["id"])
    assert due["due"] is True
    r = c.put(f"/profiles/{pid}/jamakkol/{ask['id']}/outcome", json={"outcome": "happened"})
    assert r.status_code == 200 and r.json()["outcome"] == "happened"
    assert c.put(f"/profiles/{pid}/jamakkol/{ask['id']}/outcome", json={"outcome": "maybe"}).status_code == 422
    from app import storage
    assert storage.jk_outcomes() == [{"kind": "career", "verdict": ask["verdict"], "outcome": "happened"}]
    c.delete(f"/profiles/{pid}")
    assert storage.jk_list(pid) == []
