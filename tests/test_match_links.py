"""Connections between two charts for match making (core/match_links.py)."""
from core import match_links as M


def view(lagna, **signs):
    base = {p: 0 for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")}
    base.update(signs)
    return {"lagna": lagna, "planets": {p: {"sign": s, "retro": False} for p, s in base.items()}}


SAG, GEM, LEO, ARI, PIS, SCO, VIR = 8, 2, 4, 0, 11, 7, 5
G = view(SAG, Sun=10, Moon=PIS, Mercury=PIS, Venus=PIS, Ketu=PIS, Mars=GEM, Jupiter=GEM, Saturn=LEO, Rahu=VIR)
B = view(SAG, Moon=SCO, Saturn=SCO, Rahu=PIS, Ketu=VIR, Jupiter=ARI, Sun=LEO, Mars=LEO, Mercury=LEO, Venus=LEO)


def test_the_sample_couple():
    ls = M.links(G, B, ("Arjun", "Meera"))
    titles = {l["title"]: l for l in ls}
    assert titles["Moons 5/9 apart"]["kind"] == "yellow"
    assert titles["Meera's Rahu on Arjun's Moon and Venus"]["kind"] == "yellow"
    assert titles["Arjun's Saturn on Meera's Venus"]["kind"] == "yellow"
    mars = titles["Arjun's Mars on Meera's 7th house"]
    assert mars["kind"] == "red" and mars["from"] == {"who": "groom", "name": "Arjun", "planet": "Mars", "house": 7}
    assert mars["to"] == {"who": "bride", "name": "Meera", "planet": None, "house": 7}
    assert titles["Arjun's Mars and Meera's Venus"]["kind"] == "green"
    assert titles["Meera's Jupiter blesses Arjun's Lagna"]["to"]["house"] == 1
    # green first, then yellow, then red, numbered in that order
    kinds = [l["kind"] for l in ls]
    assert kinds == sorted(kinds, key=M.ORDER.get) and [l["n"] for l in ls] == list(range(1, len(ls) + 1))
    s = M.summary(ls)
    assert s["counts"]["red"] == 1 and s["text"].startswith("Strongest link:") and "Watch: Arjun's Mars" in s["text"]


def test_moon_pairs_and_nadi():
    def moon(a, b, nadi=False):
        ls = M.links(view(0, Moon=a), view(0, Moon=b), ("A", "B"), nadi)
        return next(l for l in ls if l["from"]["planet"] == l["to"]["planet"] == "Moon")
    assert moon(0, 6)["kind"] == "green" and moon(0, 6)["title"] == "Moons 1/7 apart"
    assert moon(0, 5)["kind"] == "red"                                  # 6/8
    assert moon(0, 0)["title"] == "Moons in the same sign"
    assert moon(0, 6, nadi=True)["kind"] == "red" and "Nadi" in moon(0, 6, True)["text"]


def test_match_endpoint_carries_links(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    req = {"lat": 30.73, "lon": 76.78, "tz_name": "Asia/Kolkata"}
    g = c.post("/profiles", json={"name": "A", "dob": "1990-01-01", "tob": "06:00:00", **req}).json()["id"]
    b = c.post("/profiles", json={"name": "B", "dob": "1992-06-15", "tob": "18:30:00", **req}).json()["id"]
    r = c.post("/matchmaking", json={"groom_id": g, "bride_id": b})
    assert r.status_code == 200
    L = r.json()["links"]
    assert set(L) == {"d1", "d9"} and L["d1"]["links"] and set(L["d1"]["summary"]["counts"]) == {"green", "yellow", "red"}
