"""KP horary numbers and judgement, and the muhurat date finder."""
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app import muhurat
from app.main import app
from core import horary

CHD = {"lat": 30.7333, "lon": 76.7794}


def test_249_table_matches_kp_numbering():
    assert len(horary.KP_249) == 249
    assert horary.number_point(1) == {**horary.number_point(1), "longitude": 0.0, "star_lord": "Ketu", "sub_lord": "Ketu"}
    assert horary.number_point(2)["sub_lord"] == "Venus" and abs(horary.number_point(2)["longitude"] - 0.7778) < 1e-3
    p = horary.number_point(249)
    assert p["sign"] == "Pisces" and p["star_lord"] == "Mercury" and p["sub_lord"] == "Saturn"
    # a sub crossing a sign boundary yields two numbers: Krittika's first sub spans Aries/Taurus
    assert all(b > a for a, b in zip(horary.KP_249, horary.KP_249[1:]))
    assert 30.0 in [round(x, 6) for x in horary.KP_249]


def test_judgement_casts_the_number_as_ascendant():
    r = horary.judge(123, "marriage", datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc), **CHD)
    assert abs(r["ascendant"] - r["number"]["longitude"]) < 1e-3
    assert r["verdict"] in ("yes", "likely", "mixed", "no") and r["reasons"]
    assert r["question"]["house"] == 7 and set(r["supports"]) <= {2, 7, 11}


def test_horary_endpoint_validates():
    c = TestClient(app)
    ok = c.post("/horary", json={"number": 7, "kind": "job", **CHD, "asked_at": "2026-10-08T10:00:00+05:30"})
    assert ok.status_code == 200 and ok.json()["question"]["house"] == 10
    assert c.post("/horary", json={"number": 250, "kind": "job", **CHD}).status_code == 422
    assert c.post("/horary", json={"number": 7, "kind": "lottery", **CHD}).status_code == 422
    assert len(c.get("/horary/kinds").json()) == len(horary.QUESTIONS)


def test_finder_ranks_good_days_with_safe_windows():
    r = muhurat.find_dates("vehicle", date(2026, 10, 8), 60, 30.73, 76.79, "Asia/Kolkata", 17, 7)
    assert r["checked"] == 60 and 0 < len(r["dates"]) <= 5
    scores = [d["score"] for d in r["dates"]]
    assert scores == sorted(scores, reverse=True) and all(d["verdict"] in ("excellent", "good") for d in r["dates"])
    for d in r["dates"]:
        rk = [datetime.fromisoformat(x) for x in d["rahu_kalam"]]
        for w in d["windows"]:
            s, e = datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"])
            assert not (s < rk[1] and e > rk[0])


def test_finder_endpoint():
    c = TestClient(app)
    body = {"activity": "marriage", "start": "2026-10-08", "days": 90, "lat": 30.73, "lon": 76.79, "tz_name": "Asia/Kolkata"}
    assert c.post("/muhurat/find", json=body).json()["activity"]["key"] == "marriage"
    assert c.post("/muhurat/find", json={**body, "days": 400}).status_code == 422
    assert c.post("/muhurat/find", json={**body, "activity": "nope"}).status_code == 422
