"""Graha drishti, Neecha Bhanga and yogas on hand-built charts."""
from fastapi.testclient import TestClient

from app import guidance
from app.main import app
from core import yogas as Y

ARI, TAU, GEM, CAN, LEO, VIR, LIB, SCO, SAG, CAP, AQU, PIS = range(12)
BASE = {"Sun": ARI, "Moon": TAU, "Mars": CAP, "Mercury": ARI, "Jupiter": CAN, "Venus": PIS, "Saturn": LIB,
        "Rahu": GEM, "Ketu": SAG}
SUKH = {"Sun": LEO, "Moon": SCO, "Mars": LEO, "Mercury": LEO, "Jupiter": ARI, "Venus": LEO, "Saturn": SCO,
        "Rahu": PIS, "Ketu": VIR}


def names(ys):
    return {y["name"] for y in ys}


def test_special_aspects():
    a = Y.aspects(SUKH, SAG)
    assert a["Saturn"]["houses"] == [2, 6, 9] and set(a["Saturn"]["planets"]) == {"Sun", "Mars", "Mercury", "Venus"}
    assert a["Jupiter"]["houses"] == [1, 9, 11]
    assert a["Mars"]["houses"] == [3, 4, 12]  # 4th, 7th, 8th from Leo = Scorpio, Aquarius, Pisces
    assert a["Sun"]["houses"] == [3]  # only the 7th


def test_neecha_bhanga_cancelled_and_not():
    nb = Y.neecha_bhanga(SUKH, SAG)
    assert list(nb) == ["Moon"] and nb["Moon"]["cancelled"]
    assert any("Mars" in r for r in nb["Moon"]["reasons"]) and any("Venus" in r for r in nb["Moon"]["reasons"])
    # Sun debilitated in Libra with Venus (lord) and Saturn (exalted there) out of kendras, no aspect: not cancelled
    lone = {**BASE, "Sun": LIB, "Venus": TAU, "Saturn": LEO, "Mars": LEO, "Moon": ARI, "Jupiter": SAG}
    assert Y.neecha_bhanga(lone, GEM)["Sun"]["cancelled"] is False
    assert Y.neecha_bhanga(lone, GEM, d9={"Sun": ARI})["Sun"]["cancelled"]  # exalted in Navamsa


def test_yogas_found_in_sample_chart():
    ys = Y.analyse(SUKH, SAG, combust={"Mercury": True})["yogas"]
    assert {"Budha-Aditya", "Raja yoga", "Dhana yoga", "Sarala (Viparita Raja)"} <= names(ys)
    assert "combust" in next(y for y in ys if y["name"] == "Budha-Aditya")["meaning"]
    assert "Gaja Kesari" not in names(ys) and "Kaal Sarp" not in names(ys)


def test_classic_yogas():
    assert "Gaja Kesari" in names(Y.yogas({**BASE, "Jupiter": LEO, "Moon": TAU}, ARI))  # 4th from Moon
    assert "Hamsa (Pancha Mahapurusha)" in names(Y.yogas({**BASE, "Jupiter": CAN}, ARI))  # exalted in 4th
    assert "Yogakaraka" in names(Y.yogas(BASE, TAU))  # Saturn rules 9th and 10th for Taurus
    lonely = {"Sun": SAG, "Moon": LIB, "Mars": SAG, "Mercury": SAG, "Jupiter": SAG, "Venus": SAG, "Saturn": SAG,
              "Rahu": GEM, "Ketu": SAG}
    k = [y for y in Y.yogas(lonely, GEM) if y["name"].startswith("Kemadruma")]
    assert k and k[0]["kind"] == "challenging"
    kaal = {"Sun": ARI, "Moon": TAU, "Mars": GEM, "Mercury": ARI, "Jupiter": CAN, "Venus": TAU, "Saturn": LEO,
            "Rahu": PIS, "Ketu": VIR}
    assert "Kaal Sarp" in names(Y.yogas(kaal, ARI))


def test_chart_and_telegram_text_reflect_cancellation():
    c = TestClient(app).post("/chart", json={"dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629,
                                             "lon": 76.7884, "tz_name": "Asia/Kolkata"}).json()
    assert c["strength"]["neecha_bhanga"]["Moon"]["cancelled"]
    assert "Neecha Bhanga" in guidance.weak_planet(c)[1]
