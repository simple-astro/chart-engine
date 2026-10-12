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
    assert sum(len(x["planets"]) for x in t.values()) == 9


def test_circuits_name_partners_ahead_behind_and_exchanges():
    c = client.post("/chart", json=OWNER_LIKE).json()
    k = {x["karaka"]: x for x in c["bnn"]["circuits"]}
    assert set(k) == set(bnn.KARAKAS)
    v = k["Venus"]  # Venus in Leo with Sun, Mars, Mercury; Jupiter in the fire trine; Ketu in Virgo ahead
    assert {"Sun", "Mars", "Mercury", "Jupiter"} <= set(v["joined"]) and v["ahead"] == ["Ketu"]
    assert "in the same sign by" in v["text"][0] and "through the fire trine by Jupiter" in v["text"][0]
    assert "man's chart" in k["Jupiter"]["role"] and "woman's chart" in k["Jupiter"]["role"]  # no gender guessed
    # an exchange: Mars in Leo and Sun in Aries swap signs
    c2 = {"grahas": {**{p: {"sign_index": 6, "degrees_in_sign": 10.0} for p in bnn.ORDER},
                     "Mars": {"sign_index": 4, "degrees_in_sign": 5.0}, "Sun": {"sign_index": 0, "degrees_in_sign": 9.0}}}
    assert next(x for x in bnn.analyse(c2)["circuits"] if x["karaka"] == "Sun")["exchange"] == "Mars"


def test_sukh_gets_a_compact_bnn_line():
    c = client.post("/chart", json=OWNER_LIKE).json()
    out = synthesis.build({"chart": c, "request": {**OWNER_LIKE, "place": "Chandigarh"}})
    assert out["bnn_trines"]["Fire"].startswith("Jupiter <") and "never timing" in out["bnn_rule"]
