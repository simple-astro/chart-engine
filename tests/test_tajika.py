"""Tajika (Varshaphal): Varsha Pravesh, Muntha, year lord, Tajika aspects and Mudda dasha (core/tajika.py)."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import constants as C, tajika as T
from core.ephemeris import julian_day
from core.grahas import compute_grahas

MODI = {"name": "Modi", "dob": "1950-09-17", "tob": "11:00:00", "lat": 23.7869, "lon": 72.6385,
        "tz_name": "Asia/Kolkata", "ayanamsha": "lahiri"}


@pytest.fixture(scope="module")
def chart():
    return TestClient(app).post("/chart", json=MODI).json()


def test_varsha_pravesh_is_the_suns_return_to_its_birth_degree(chart):
    r = T.annual(chart, MODI, 76)
    vp = datetime.fromisoformat(r["varsha_pravesh"])
    sun = compute_grahas(julian_day(vp), "lahiri")["Sun"].longitude
    assert abs(sun - chart["grahas"]["Sun"]["longitude"]) < 1e-4
    assert r["local"].startswith("2026-09-17") and not r["day"]          # 22:26 IST: a night return
    assert datetime.fromisoformat(r["next"]).year == 2027
    assert T.annual(chart, MODI, 0)["varsha_pravesh"].startswith("1950-09-17T05:30")  # the birth moment itself


def test_muntha_moves_one_sign_a_year(chart):
    L = chart["lagna"]["sign_index"]                                     # Scorpio
    for n in (0, 1, 12, 76):
        m = T.annual(chart, MODI, n)["muntha"]
        assert m["sign_index"] == (L + n) % 12 and m["lord"] == C.SIGN_LORDS[(L + n) % 12]
    assert T.annual(chart, MODI, 76)["muntha"]["sign"] == "Pisces"


def test_office_bearers_and_year_lord(chart):
    r = T.annual(chart, MODI, 76)
    board = {b["office"]: b["planet"] for b in r["office_bearers"]}
    assert board["Birth Lagna lord"] == "Mars" and board["Muntha lord"] == "Jupiter"
    assert board["Annual Lagna lord"] == C.SIGN_LORDS[r["lagna"]["sign_index"]]
    assert board["Tri-rashi lord"] == T.TRI_RASHI[r["lagna"]["sign_index"]][1]            # a night return
    assert board["Sun or Moon sign lord"] == C.SIGN_LORDS[r["planets"]["Moon"]["sign_index"]]
    # the year lord aspects the annual Lagna and nothing aspecting it is stronger
    yl = next(b for b in r["office_bearers"] if b["planet"] == r["year_lord"]["planet"])
    assert yl["aspects_lagna"] and all(b["strength"] <= yl["strength"] for b in r["office_bearers"] if b["aspects_lagna"])
    assert r["year_lord"]["planet"] == "Jupiter"


def test_tajika_aspects_by_sign_with_orbs():
    p = lambda n, lon: {"name": n, "longitude": lon, "sign_index": int(lon // 30)}
    assert T.tajika_aspect(p("Sun", 10), p("Moon", 130))["kind"] == "trine"
    assert T.tajika_aspect(p("Sun", 10), p("Moon", 130))["within_orbs"]                   # exactly 120°
    assert T.tajika_aspect(p("Sun", 10), p("Moon", 70))["nature"] == "friendly"           # sextile
    assert T.tajika_aspect(p("Mars", 10), p("Saturn", 100))["nature"] == "inimical"       # square
    assert T.tajika_aspect(p("Mars", 10), p("Saturn", 40)) is None                        # 2/12: no aspect
    far = T.tajika_aspect(p("Venus", 0), p("Mercury", 149))                               # trine by sign, 29° off
    assert far["kind"] == "trine" and not far["within_orbs"]


def test_mudda_dasha_fills_the_year_in_vimshottari_order(chart):
    r = T.annual(chart, MODI, 76)
    md = r["mudda_dasha"]
    # Moon in Anuradha (Saturn's star) + 76 nakshatras = Uttara Phalguni, the Sun's star
    assert md[0]["lord"] == "Sun" and md[-1]["lord"] == "Sun" and len(md) == 10
    assert [x["lord"] for x in md[:9]] == ["Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury", "Ketu", "Venus"]
    assert md[0]["start"] == r["varsha_pravesh"] and md[-1]["end"] == r["next"]
    assert all(a["end"] == b["start"] for a, b in zip(md, md[1:]))


def test_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=MODI).json()["id"]
    now = c.get(f"/profiles/{pid}/tajika").json()
    assert now["current"] and now["varsha_pravesh"] <= datetime.now().astimezone().isoformat() < now["next"]
    assert c.get(f"/profiles/{pid}/tajika?years=10").json()["years"] == 10
    assert c.get(f"/profiles/{pid}/tajika?years=200").status_code == 422


def test_saham_formula_and_the_30_degree_rule():
    assert T.saham(100, 40, 70) == 130            # C (70) lies between B (40) and A (100): plain A - B + C
    assert T.saham(100, 40, 10) == (100 - 40 + 10 + 30) % 360   # C outside B..A: add 30°


def test_sahams_reverse_at_night(chart):
    r = T.annual(chart, MODI, 76)                  # a night return
    punya = next(x for x in r["sahams"] if x["name"] == "Punya")
    assert punya["formula"] == "Sun - Moon + Asc"
    vivaha = next(x for x in r["sahams"] if x["name"] == "Vivaha")
    assert vivaha["formula"] == "Venus - Saturn + Asc"           # Vivaha does not reverse
    assert all(1 <= x["house"] <= 12 for x in r["sahams"]) and len(r["sahams"]) == len(T.SAHAMS)


def _planets(**pos):
    """name -> (longitude, speed[, retrograde]) for the seven planets; houses from an Aries Lagna."""
    out = {}
    for n in T.SEVEN:
        lon, speed, *r = pos.get(n, (200.0 + T.SEVEN.index(n), 0.5))
        si = int(lon // 30)
        out[n] = {"name": n, "longitude": lon, "sign_index": si, "house": si + 1, "speed": speed,
                  "retrograde": bool(r and r[0]), "combust": False, "dignity": "neutral"}
    return out


def test_ithasala_ishrafa_and_radda():
    # Mercury (fast) at 10° Aries, Jupiter (slow) at 15° Leo: a trine, applying
    p = _planets(Mercury=(10.0, 1.2), Jupiter=(135.0, 0.1))
    ys = {(y["yoga"], tuple(y["planets"])) for y in T.yogas(p)}
    assert ("Ithasala", ("Mercury", "Jupiter")) in ys
    p = _planets(Mercury=(20.0, 1.2), Jupiter=(135.0, 0.1))      # Mercury already past Jupiter's degree
    assert ("Ishrafa", ("Mercury", "Jupiter")) in {(y["yoga"], tuple(y["planets"])) for y in T.yogas(p)}
    p = _planets(Mercury=(10.0, 1.2), Jupiter=(135.0, 0.1, True))  # Jupiter retrograde: spoiled
    assert ("Radda", ("Mercury", "Jupiter")) in {(y["yoga"], tuple(y["planets"])) for y in T.yogas(p)}


def test_nakta_links_two_planets_through_a_faster_one():
    # Mars (Aries 15°) and Saturn (Scorpio 15°): 6/8, no aspect. The fast Moon (Cancer 10°) applies to both:
    # a square to Mars (5° off) and a trine to Saturn (5° off).
    p = _planets(Mars=(15.0, 0.6), Saturn=(225.0, 0.05), Moon=(100.0, 13.0))
    assert any(y["yoga"] == "Nakta" and set(y["planets"]) == {"Mars", "Saturn", "Moon"} for y in T.yogas(p))


def test_ikkabala_and_induvara():
    strong = _planets(**{n: (30.0 * h + 5, 0.5) for n, h in zip(T.SEVEN, [0, 3, 6, 9, 1, 4, 7])})
    assert T.yogas(strong)[0]["yoga"] == "Ikkabala"
    weak = _planets(**{n: (30.0 * h + 5, 0.5) for n, h in zip(T.SEVEN, [2, 5, 8, 11, 2, 5, 8])})
    assert T.yogas(weak)[0]["yoga"] == "Induvara"
