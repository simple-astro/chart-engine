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
                   "Moon": ("Leo", 127), "Snake": ("Gemini", 82)}
    c = J.cast(t, 13.0827, 80.2707, "Asia/Kolkata")
    assert c["period"] == "night" and c["udayam"]["sign"] == "Aries" and 8.5 < c["udayam"]["deg"] < 11
    assert (c["arudam"]["sign"], round(c["arudam"]["deg"], 1)) == ("Cancer", 1.9)      # shown as 1°54'
    assert c["kavippu"]["sign"] == "Aquarius"
    # another app's chart, Saturday 17 Oct 11:35: the same jama degrees
    j = J.jama_positions(at(2026, 10, 17, 11, 35, 52), "America/Winnipeg")
    assert (j["weekday"], j["number"], j["ruler"]) == ("Saturday", 4, "Jupiter")
    assert {p: round(x["lon"]) for p, x in j["planets"].items()} == {
        "Jupiter": 327, "Mercury": 282, "Venus": 237, "Saturn": 192, "Moon": 147, "Snake": 102, "Sun": 57, "Mars": 12}


def test_matches_divya_chakshu_to_the_arc_minute():
    """Divya Chakshu, Bhopal, Monday 19 Oct 2026 09:34 IST: Lahiri and Hindu sunrise for the Udayam."""
    c = J.cast(at(2026, 10, 19, 9, 34, tz="Asia/Kolkata"), 23.2599, 77.4126, "Asia/Kolkata")
    dms = lambda d, m, s: d + m / 60 + s / 3600
    # (their Rahu is the true node and their Maandi uses another sunrise; we follow the reference calculator there)
    want = {"udayam": dms(281, 58, 23), "arudam": dms(204, 0, 0), "kavippu": dms(125, 59, 58)}
    for k, v in want.items():
        assert abs((c[k]["lon"] - v + 180) % 360 - 180) < 1 / 60, k          # within 1'
    sky = {"Sun": dms(181, 33, 55), "Moon": dms(276, 57, 53), "Mars": dms(107, 41, 6), "Mercury": dms(205, 13, 1),
           "Jupiter": dms(118, 21, 20), "Venus": dms(189, 28, 27), "Saturn": dms(345, 56, 3)}
    for p, v in sky.items():
        assert abs((c["transit"][p]["lon"] - v + 180) % 360 - 180) < 1 / 60, p   # Moshier vs their ephemeris: < 1'
    assert "Ketu" not in c["transit"]                                         # Jamakkol reads Rahu only
    assert {p: round(x["lon"]) for p, x in c["jama"]["planets"].items()} == {
        "Sun": 163, "Mars": 118, "Jupiter": 73, "Mercury": 28, "Venus": 343, "Saturn": 298, "Moon": 253, "Snake": 208}
    conf = dict(J.confirmation(c))
    assert conf["Jama planet that crossed the Udayam"] == "Moon" and conf["Jama planet approaching the Udayam"] == "Saturn"
    assert conf["Udayam to Arudam (house)"] == "10" and conf["Udayam to Kavippu (house)"] == "8"
    assert conf["Exchanges, inner with jama"] == "Jupiter–Moon"
    assert conf["Kavippu is catching"] == "Mars"   # the jama Mars (118°), not Ketu in the sky (123°)


def test_matches_the_reference_calculator():
    """The owner's reference calculator (Jamakkol Horary: Lahiri, Hindu sunrise, mean node), Winnipeg,
    Monday 19 Oct 2026 10:09:23 CDT. Every point within 1′."""
    c = J.cast(at(2026, 10, 19, 10, 9, 23), *WPG)
    L = lambda s, d, m, sec: ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius",
                              "Capricorn", "Aquarius", "Pisces"].index(s) * 30 + d + m / 60 + sec / 3600
    want = {"udayam": L("Sagittarius", 15, 31, 0), "arudam": L("Taurus", 26, 18, 0), "kavippu": L("Sagittarius", 3, 42, 0),
            "maandi": L("Capricorn", 9, 36, 31)}
    sky = {"Sun": L("Libra", 2, 1, 14), "Moon": L("Capricorn", 12, 30, 45), "Mercury": L("Libra", 25, 27, 51),
           "Venus": L("Libra", 9, 13, 4), "Mars": L("Cancer", 17, 55, 56), "Jupiter": L("Cancer", 28, 25, 17),
           "Saturn": L("Pisces", 15, 54, 22), "Rahu": L("Aquarius", 2, 29, 49)}
    near = lambda a, b: abs((a - b + 180) % 360 - 180) < 1 / 60
    for k, v in want.items():
        assert near(c[k]["lon"], v), k
    for p, v in sky.items():
        assert near(c["transit"][p]["lon"], v), p
    jama = {"Venus": L("Aquarius", 25, 18, 30), "Saturn": L("Capricorn", 10, 18, 30), "Moon": L("Scorpio", 25, 18, 30),
            "Snake": L("Libra", 10, 18, 30), "Sun": L("Leo", 25, 18, 30), "Mars": L("Cancer", 10, 18, 30),
            "Jupiter": L("Taurus", 25, 18, 30), "Mercury": L("Aries", 10, 18, 30)}
    for p, v in jama.items():
        assert near(c["jama"]["planets"][p]["lon"], v), p
    assert c["period_start"].startswith("2026-10-19T13:02") and c["period_end"].startswith("2026-10-19T23:23")  # 08:02 / 18:23


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
    assert g["confirm"][0].startswith("The 10th lord ") and "bhava connections" in g["confirm"][0]
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


def test_maandi_is_the_degree_rising_when_maandi_rises():
    # The reference calculator (Winnipeg, Monday 19 Oct 2026 10:09:23 CDT): Maandi Capricorn 9°36′31″. Monday by day
    # Maandi rises 22 ghatis (of 30) after the Hindu sunrise; the Lahiri ascendant then.
    c = J.cast(at(2026, 10, 19, 10, 9, 23), *WPG)
    assert c["maandi"]["sign"] == "Capricorn" and abs(c["maandi"]["lon"] - (270 + 9 + 36 / 60 + 31 / 3600)) < 1 / 60
    assert c["maandi"]["rises"] == "15:38"


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
    body = {"kind": "career", "question": "Will I get the bank job?", "lat": 49.9, "lon": -97.1, "tz_name": "America/Winnipeg",
            "place": "Winnipeg, Manitoba, Canada"}
    first = c.post(f"/profiles/{pid}/jamakkol", json=body)
    assert first.status_code == 200 and first.json()["ask"]["due"] is False
    assert first.json()["ask"]["place"] == "Winnipeg, Manitoba, Canada"
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


# ----- 10th / 11th lord links, inner root vs jama branch, and timing by rays -----
from core.dignity import dignity


def _chart(U=0, A=4, K=7, M=5, jama=None, inner=None, retro=()):
    """A hand-built chart: Udayam in sign U (at 15°), every planet parked in Virgo unless placed."""
    pt = lambda s, d=15.0: {"sign_index": s, "lon": s * 30 + d}
    j = {p: pt(5, 20.0 + i) for i, p in enumerate(J.JAMA)}
    j.update({p: pt(*v) if isinstance(v, tuple) else pt(v) for p, v in (jama or {}).items()})
    t = {}
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]:
        s = (inner or {}).get(p, 5)
        t[p] = {**pt(s), "dignity": dignity(p, s), "retrograde": p in retro}
    return {"udayam": pt(U), "arudam": pt(A), "kavippu": pt(K), "maandi": pt(M), "jama": {"planets": j}, "transit": t}


def test_tenth_lord_in_the_udayam_or_exchanging_is_success():
    # Aries Udayam: Saturn rules the 10th (Capricorn). Inner Saturn in Aries is debilitated, so use Leo Udayam:
    # 10th = Taurus (Venus), 11th = Gemini (Mercury), Udayam lord the Sun.
    c = _chart(U=4, inner={"Venus": 4})
    assert [x["text"] for x in J.lord_links(c)] == ["The 10th lord (the base of the question) Venus sits in the Udayam."]
    assert any("Venus sits in the Udayam: success" in x for x in J.read(c, "career")["for"])
    c = _chart(U=4, inner={"Venus": 4, "Sun": 1})       # the Sun in Taurus while Venus is in Leo: an exchange
    assert "exchanges signs with the Udayam lord Sun" in J.lord_links(c)[0]["text"]
    c = _chart(U=4, inner={"Mercury": 10})              # the 11th lord opposite the Udayam
    assert J.lord_links(c)[0]["text"] == "The 11th lord (gains) Mercury aspects the Udayam from the 7th."


def test_a_debilitated_lord_cannot_deliver():
    c = _chart(U=4, inner={"Mercury": 11})              # Mercury debilitated in Pisces, but not opposite Leo
    assert not J.lord_links(c)
    c = _chart(U=2, inner={"Jupiter": 2})               # Gemini Udayam: Jupiter rules the 10th (Pisces)
    x = J.lord_links(c)[0]
    assert x["lord"] == "Jupiter" and not x["weak"]
    c = _chart(U=9, inner={"Venus": 5})                 # Capricorn Udayam: Venus (10th lord) debilitated in Virgo...
    c["transit"]["Venus"]["sign_index"] = 3             # ...placed opposite the Udayam in Cancer and marked weak
    c["transit"]["Venus"]["dignity"] = "debilitated"
    r = J.read(c, "career")
    assert any("but it is debilitated: it cannot deliver" in x for x in r["against"])
    assert not any("Venus aspects the Udayam from the 7th: success" in x for x in r["for"])


def test_jama_branch_counts_only_with_its_inner_root():
    # Leo Udayam; the jama Venus (10th lord) is approaching the Udayam
    c = _chart(U=4, jama={"Venus": (4, 20.0)}, inner={"Venus": 2})     # inner Venus in Gemini: a healthy root
    for p in J.JAMA:
        if p != "Venus":
            c["jama"]["planets"][p] = {"sign_index": 5, "lon": 5 * 30 + 25}
    assert any("jama planet" in x["text"] for x in J.lord_links(c))
    c["transit"]["Venus"].update(sign_index=5, dignity="debilitated")   # its inner planet is debilitated
    assert not any("jama planet" in x["text"] for x in J.lord_links(c))
    r = J.read(c, "general")
    assert any("the branch has no root" in x for x in r["against"])


def test_timing_uses_the_questions_planet_and_its_rays():
    # Marriage: Venus (rays 20). Inner Venus in Libra (own): × 2. Jama Venus 3 signs from an Aries Udayam.
    c = _chart(U=0, jama={"Venus": 2}, inner={"Venus": 6})
    t = J.ray_timing(c, ["Venus", "Mercury"])
    assert t["planet"] == "Venus" and t["days"] == 20 * 2 * 3 and "× 2 (own sign)" in t["text"]
    t = J.ray_timing(_chart(U=0, jama={"Venus": 2}, inner={"Venus": 11}), ["Venus"])          # exalted in Pisces
    assert t["days"] == 20 * 3 * 3
    t = J.ray_timing(_chart(U=0, jama={"Venus": 2}, inner={"Venus": 6}, retro=("Venus",)), ["Venus"])
    assert t["days"] == 20 * 2 / 2 * 3 and "÷ 2 (retrograde)" in t["text"]
    t = J.ray_timing(_chart(U=0, K=2, jama={"Venus": 2}, inner={"Venus": 6}), ["Venus"])      # with the Kavippu
    assert "÷ 2 (with the Kavippu)" in t["text"]
    t = J.ray_timing(_chart(U=0, jama={"Moon": 1}), [])                                      # no significator
    assert t["planet"] == "Moon" and t["days"] == 21 * 2 and "no significator" in t["text"]


def test_ray_powers_grid_matches_divya_chakshu():
    """Divya Chakshu's Ray Powers, Bhopal, Monday 19 Oct 2026 09:58 IST: every cell of the grid, and the rays."""
    c = J.cast(at(2026, 10, 19, 9, 58, tz="Asia/Kolkata"), 23.2599, 77.4126, "Asia/Kolkata")
    assert J.RAYS == {"Sun": 5, "Moon": 21, "Mars": 8, "Mercury": 16, "Jupiter": 10, "Venus": 20, "Saturn": 4,
                      "Snake": 6, "Rahu": 4}
    want = {  # columns: Su Mo Ma Me Ju Ve Sa Ra
        "Sun": [60, 45, 15, 60, 15, 60, 35, 40], "Moon": [63, 252, 126, 63, 126, 63, 210, 231],
        "Mars": [80, 56, 8, 80, 8, 80, 40, 48], "Mercury": [112, 64, 160, 112, 160, 112, 32, 48],
        "Jupiter": [90, 60, 120, 90, 120, 90, 40, 50], "Venus": [120, 60, 180, 120, 180, 120, 20, 40],
        "Saturn": [16, 4, 28, 16, 28, 16, 44, 48], "Snake": [6, 60, 24, 6, 24, 6, 48, 54]}
    got = {row["jama"]: [row["cells"][i] for i in J.INNER] for row in J.ray_matrix(c)}
    assert got == want


def test_timing_has_a_ray_for_every_significator():
    c = _chart(U=0, jama={"Saturn": 3}, inner={"Saturn": 6})        # Saturn exalted in Libra: 4 × 3, 4 signs
    t = J.ray_timing(c, ["Saturn"])
    assert t["planet"] == "Saturn" and t["days"] == 4 * 3 * 4
    t = J.ray_timing(_chart(U=0, jama={"Snake": 2}, inner={"Rahu": 4}), ["Snake"])   # travel: the Snake's own ray
    assert t["planet"] == "Snake" and t["days"] == 6 * 3


@pytest.mark.parametrize("place,h,m,want", [
    ((23.2599, 77.4126), 9, 34, [3, 1, 2]),      # Bhopal: jama Venus in Uttara Bhadrapada (Saturn: houses 1, 2)
    ((23.2599, 77.4126), 9, 58, [3, 12, 3]),     # Bhopal: jama Venus in Purva Bhadrapada (Jupiter: houses 12, 3)
    ((28.6139, 77.2090), 10, 10, [2, 12, 3]),    # New Delhi: jama Venus in Aquarius, Purva Bhadrapada
    ((30.7333, 76.7794), 21, 43, [3, 1, 2]),     # Chandigarh, night
])
def test_tenth_lord_bhava_connections_match_divya_chakshu(place, h, m, want):
    """Divya Chakshu, 19 Oct 2026: the jama 10th lord's house, then the houses its star lord rules."""
    c = J.cast(at(2026, 10, 19, h, m, tz="Asia/Kolkata"), *place, "Asia/Kolkata")
    assert J.tenth_lord_connections(c)["houses"] == want
    row = dict(J.confirmation(c))["10th lord bhava connections"]
    assert row.startswith(" ".join(map(str, want)) + " (Venus: jama in house")
    assert "is the base of the question" in J.read(c, "career")["confirm"][0]


def test_sign_rays_as_divya_chakshu():
    assert J.SIGN_RAYS == [8, 8, 5, 3, 8, 11, 2, 4, 6, 8, 8, 27]
    r = J.jamakkol("general", at(2026, 10, 19, 21, 43, tz="Asia/Kolkata"), 30.7333, 76.7794, "Asia/Kolkata")
    assert r["sign_rays"]["Pisces"] == 27 and r["sign_rays"]["Aquarius"] == 8 and len(r["sign_rays"]) == 12
