"""Yogas with the three checks: net strength, dasha activation and cancellation (core/yoga_eval.py)."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from core import yoga_eval as E

ARI, TAU, GEM, CAN, LEO, VIR, LIB, SCO, SAG, CAP, AQU, PIS = range(12)
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def chart(signs: dict, lagna: int, degs: dict | None = None, combust=(), dasha=None) -> dict:
    degs = degs or {}
    g = {p: {"sign_index": s, "degrees_in_sign": degs.get(p, 15.0), "longitude": s * 30 + degs.get(p, 15.0),
             "combust": p in combust} for p, s in signs.items()}
    return {"grahas": g, "lagna": {"sign_index": lagna}, "vargas": {}, "dasha": dasha or []}


BASE = {"Sun": ARI, "Moon": CAN, "Mars": SAG, "Mercury": TAU, "Jupiter": AQU, "Venus": PIS, "Saturn": SCO,
        "Rahu": GEM, "Ketu": SAG}
names = lambda r: [y["name"] for y in r["yogas"]]


def test_new_yogas_are_found():
    # Mars 2nd and Jupiter 12th from the Moon -> Durudhara (not Sunapha); Jupiter 10th from the Lagna -> Amala;
    # Jupiter with Rahu -> Guru-Chandal
    s = {**BASE, "Mars": LEO, "Jupiter": GEM}
    r = E.evaluate(chart(s, VIR), NOW)
    assert {"Durudhara", "Amala", "Guru-Chandal"} <= set(names(r)) and "Sunapha" not in names(r)
    assert "Sunapha" in names(E.evaluate(chart({**BASE, "Mars": LEO}, VIR), NOW))
    gc = next(y for y in r["yogas"] if y["name"] == "Guru-Chandal")
    assert gc["kind"] == "challenging" and gc["category"] == "Challenge"
    assert not any(w in gc["meaning"].lower() for w in ("curse", "ruin", "disaster"))


def test_a_pure_dusthana_lord_weakens_but_a_trikona_lord_does_not():
    assert "Mars" not in E._dusthana_lords(SAG)   # Mars rules the 5th and 12th for Sagittarius: not counted
    assert "Venus" in E._dusthana_lords(SAG)       # Venus rules the 6th and 11th: counted


def test_mercury_combustion_counts_only_within_3_degrees():
    s = {**BASE, "Mercury": ARI}
    near = chart(s, LEO, degs={"Sun": 15.0, "Mercury": 13.5}, combust=("Mercury",))
    far = chart(s, LEO, degs={"Sun": 15.0, "Mercury": 5.0}, combust=("Mercury",))
    assert E._combust(near["grahas"], "Mercury") and not E._combust(far["grahas"], "Mercury")


def test_deep_sun_debilitation_cancels_raja_yogas():
    # Taurus lagna: Saturn is the yogakaraka (9th + 10th lord); the Sun at 8 deg Libra cancels Raja-type yogas
    r = E.evaluate(chart({**BASE, "Sun": LIB}, TAU, degs={"Sun": 8.0}), NOW)
    yk = next(y for y in r["yogas"] if y["name"] == "Yogakaraka")
    assert r["bhanga"] and yk["status"] == "Cancelled" and "deep debilitation" in yk["cancelled_by"][0]
    r2 = E.evaluate(chart({**BASE, "Sun": LIB}, TAU, degs={"Sun": 20.0}), NOW)
    assert not r2["bhanga"]


def test_a_yoga_is_active_only_in_its_planets_dasha():
    dasha = [{"lord": "Saturn", "start": "2020-01-01", "end": "2039-01-01",
              "children": [{"lord": "Mercury", "start": "2025-01-01", "end": "2027-09-01"},
                           {"lord": "Ketu", "start": "2027-09-01", "end": "2028-10-01"}]},
             {"lord": "Mercury", "start": "2039-01-01", "end": "2056-01-01", "children": []}]
    r = E.evaluate(chart(BASE, TAU, dasha=dasha), NOW)
    yk = next(y for y in r["yogas"] if y["name"] == "Yogakaraka")      # Saturn's own Mahadasha
    assert yk["active"] and yk["active_by"] == "Mahadasha of Saturn"
    assert r["running"] == {"Mahadasha": "Saturn", "Antardasha": "Mercury"}


def test_real_chart_has_checked_yogas_on_the_chart():
    c = TestClient(app).post("/chart", json={"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794,
                                              "tz_name": "Asia/Kolkata"}).json()
    yc = c["yoga_check"]
    assert yc["yogas"] and set(yc["counts"]) == {"good", "challenging", "active"}
    for y in yc["yogas"]:
        assert y["status"] in ("Strong", "Mixed", "Weak", "Cancelled", "Eased", "Present")
        assert y["category"] in E.ORDER
    ba = next(y for y in yc["yogas"] if y["name"] == "Budha-Aditya")   # Mercury ~11 deg from the Sun: not weakened
    assert ba["status"] == "Strong"


def test_neecha_bhanga_rule_4_mutual_kendra_of_the_two_lords():
    from core import yogas as Y
    # Sun debilitated in Libra. Venus (Libra's lord) in Gemini and Mars (lord of Aries, the Sun's exaltation)
    # in Virgo are kendras from each other, but neither is a kendra from the Lagna (Aries) or the Moon (Taurus).
    s = {"Sun": LIB, "Moon": TAU, "Mars": VIR, "Mercury": SAG, "Jupiter": LEO, "Venus": GEM, "Saturn": GEM,
         "Rahu": PIS, "Ketu": VIR}
    nb = Y.neecha_bhanga(s, ARI)["Sun"]
    assert nb["cancelled"] and nb["reasons"] == ["Venus and Mars, lords of the sign it falls in and of its exaltation "
                                                 "sign, sit in kendras from each other"]
