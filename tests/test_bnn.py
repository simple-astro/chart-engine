"""Bhrigu Nandi Nadi view: element trines in degree order and karaka circuits (readings only)."""
from fastapi.testclient import TestClient

from app import synthesis
from app.main import app
from core import bnn

client = TestClient(app)
OWNER_LIKE = {"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


def test_trines_group_by_element_in_degree_order():
    c = client.post("/chart", json=OWNER_LIKE).json()
    t = {x["element"]: x for x in c["bnn"]["trines"]}
    assert sorted(t) == ["Air", "Earth", "Fire", "Water"]
    fire = [p["planet"] for p in t["Fire"]["planets"]]  # Jupiter in Aries; Sun, Mars, Mercury, Venus in Leo
    assert set(fire) == {"Jupiter", "Mars", "Sun", "Venus", "Mercury"} and fire[0] == "Jupiter"
    degs = [p["degree"] for p in t["Fire"]["planets"]]
    assert degs == sorted(degs)
    # 9 planets, plus retrograde Jupiter (Aries) counted again in Pisces, the sign before (BNN rule)
    assert sum(len(x["planets"]) for x in t.values()) == 10
    water = [(p["planet"], p["sign"], p["also"]) for p in t["Water"]["planets"]]
    assert ("Jupiter", "Pisces", True) in water and ("Jupiter", "Aries", False) in [(p["planet"], p["sign"], p["also"]) for p in t["Fire"]["planets"]]


def test_circuits_name_partners_ahead_behind_and_exchanges():
    c = client.post("/chart", json=OWNER_LIKE).json()
    k = {x["karaka"]: x for x in c["bnn"]["circuits"]}
    assert set(k) == set(bnn.KARAKAS)
    v = k["Venus"]  # Venus in Leo with Sun, Mars, Mercury; Jupiter in the fire trine; Ketu in Virgo ahead
    assert {"Sun", "Mars", "Mercury", "Jupiter"} <= set(v["joined"]) and v["ahead"] == ["Ketu"]
    assert "in the same sign by" in v["text"][0] and "through the fire trine by Jupiter" in v["text"][0]
    assert any("What comes next: Ketu is in the next sign, so for your relationships, wealth and comforts the direction "
               "of travel is toward research, detachment and letting go" in x for x in v["text"])
    assert any(x.startswith("What stands behind it: Rahu") and "foreign influence" in x for x in k["Jupiter"]["text"])
    assert not any("Ahead of it" in x or "Behind it" in x for c_ in c["bnn"]["circuits"] for x in c_["text"])
    assert "man's chart" in k["Jupiter"]["role"] and "woman's chart" in k["Jupiter"]["role"]  # no gender guessed
    # an exchange: Mars in Leo and Sun in Aries swap signs
    c2 = {"grahas": {**{p: {"sign_index": 6, "degrees_in_sign": 10.0} for p in bnn.ORDER},
                     "Mars": {"sign_index": 4, "degrees_in_sign": 5.0}, "Sun": {"sign_index": 0, "degrees_in_sign": 9.0}}}
    assert next(x for x in bnn.analyse(c2)["circuits"] if x["karaka"] == "Sun")["exchange"] == "Mars"


def test_sukh_gets_a_compact_bnn_line():
    c = client.post("/chart", json=OWNER_LIKE).json()
    out = synthesis.build({"chart": c, "request": {**OWNER_LIKE, "place": "Chandigarh"}})
    assert out["bnn_trines"]["Fire"].startswith("Jupiter <") and "never timing" in out["bnn_rule"]


def _chart(**planets):
    """All planets in Libra at 10° unless given as (sign, degree[, retrograde])."""
    g = {p: {"sign_index": 6, "degrees_in_sign": 10.0, "retrograde": p in ("Rahu", "Ketu")} for p in bnn.ORDER}
    for p, v in planets.items():
        g[p] = {"sign_index": v[0], "degrees_in_sign": v[1], "retrograde": len(v) > 2 and v[2]}
    return {"grahas": g}


def test_retrograde_planet_also_acts_from_the_sign_before():
    # Saturn retrograde in Taurus also counts in Aries: it joins the fire trine and Mars (Leo) through it
    c = _chart(Saturn=(1, 12.0, True), Mars=(4, 3.0), Sun=(9, 20.0))
    t = {x["element"]: x for x in bnn.analyse(c)["trines"]}
    assert [(p["planet"], p["sign"], p["also"]) for p in t["Fire"]["planets"]] == [("Mars", "Leo", False), ("Saturn", "Aries", True)]
    assert ("Saturn", "Taurus", False) in [(p["planet"], p["sign"], p["also"]) for p in t["Earth"]["planets"]]
    sat = next(x for x in bnn.analyse(c)["circuits"] if x["karaka"] == "Saturn")
    assert sat["retro"] and sat["also_sign"] == "Aries" and sat["from_also"]["joined"] == ["Mars"]
    assert any(x.startswith("Saturn is retrograde, so by the BNN rule it also gives the results of Aries") and "Mars" in x
               for x in sat["text"])
    # ...and other karakas see it there: Mars is joined by retrograde Saturn through the fire trine
    mars = next(x for x in bnn.analyse(c)["circuits"] if x["karaka"] == "Mars")
    assert "Saturn" in mars["joined"] and any("retrograde Saturn" in x for x in mars["text"])


def test_rahu_and_ketu_are_not_moved_back():
    t = bnn.analyse(_chart())["trines"]
    assert not any(p["also"] for x in t for p in x["planets"])
    assert sum(len(x["planets"]) for x in t) == 9
