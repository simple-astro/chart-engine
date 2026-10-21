"""Match making: both charts (D1 and D9) for drawing, and the Moon-to-Moon highlights."""
from fastapi.testclient import TestClient

from app.main import app
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import matchmaking as mm

A = {"name": "Arjun", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}
B = {"name": "Bina", "dob": "1992-11-02", "tob": "06:10:00", "lat": 19.076, "lon": 72.8777, "tz_name": "Asia/Kolkata"}
C = {"name": "Chitra", "dob": "1993-02-20", "tob": "09:45:00", "lat": 19.076, "lon": 72.8777, "tz_name": "Asia/Kolkata"}


def _c(r):
    return compute_chart(ChartRequest(**r))


def test_pairs_are_symmetric():
    assert all(mm._pair(a) == mm._pair((14 - a) % 12 or 12) for a in range(1, 13))
    assert {mm._pair(a) for a in range(1, 13)} == set(mm.PAIR_LINE)


def test_highlights_rest_on_the_charts():
    g, b = _c(A), _c(C)
    r = mm.compute_match(g, b)
    links = {x["title"]: x for x in r["moon_links"]}
    assert set(links) >= {"Moon to Moon", "Birth stars", "Moon-sign lords", "Moons in the navamsa (D9)", "How each Moon feels",
                          "Chitra's Moon in Arjun's chart", "Arjun's Moon in Chitra's chart"}
    assert all(x["kind"] in ("good", "ok", "care") and x["text"] and x["why"] for x in r["moon_links"])
    gs, bs = g["grahas"]["Moon"]["sign_index"], b["grahas"]["Moon"]["sign_index"]
    d = (gs - bs) % 12 + 1
    assert mm.PAIR_LINE[mm._pair(d)][1] == links["Moon to Moon"]["text"]
    bhakoot = next(k for k in r["kootas"] if k["name"] == "Bhakoot")
    assert (links["Moon to Moon"]["kind"] == "care") == (bhakoot["got"] == 0)     # agrees with the koota score
    h = (bs - g["lagna"]["sign_index"]) % 12 + 1
    assert f"{mm._ord(h)} house" in links["Chitra's Moon in Arjun's chart"]["text"]


def test_vargottama_and_same_sign():
    g, b = _c(A), _c(B)
    links = {x["title"]: x for x in mm.compute_match(g, b)["moon_links"]}
    if g["grahas"]["Moon"]["sign_index"] == b["grahas"]["Moon"]["sign_index"]:
        assert links["Moon to Moon"]["why"].startswith("Both Moons are in")
    vg = g["grahas"]["Moon"]["sign_index"] == g["vargas"]["D9"]["Moon"]["sign_index"]
    assert ("Arjun has a Vargottama Moon" in links["Moons in the navamsa (D9)"]["text"]) is vg


def test_charts_for_drawing():
    g = _c(A)
    v = mm.chart_view(g)
    assert v["d1"]["lagna"] == g["lagna"]["sign_index"] and set(v["d1"]["planets"]) == set(g["grahas"])
    assert v["d9"]["planets"]["Moon"]["sign"] == g["vargas"]["D9"]["Moon"]["sign_index"] and 0 <= v["d9"]["lagna"] < 12
    assert v["tob_unknown"] is False


def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    gid, bid = (c.post("/profiles", json=x).json()["id"] for x in (A, C))
    d = c.post("/matchmaking", json={"groom_id": gid, "bride_id": bid}).json()
    assert len(d["moon_links"]) == 7 and set(d["charts"]) == {"groom", "bride"}
    assert set(d["charts"]["bride"]) == {"d1", "d9", "tob_unknown"}
