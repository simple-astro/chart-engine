"""A chart can choose its house system; without one it keeps the ayanamsha's default."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BIRTH = {"dob": "1990-03-15", "tob": "06:20:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


def chart(**kw):
    r = client.post("/chart", json={**BIRTH, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def cusps(c):
    return [h["longitude"] for h in c["houses"]]


def test_default_follows_the_ayanamsha():
    assert chart()["meta"]["house_system"] == "placidus"
    assert chart(ayanamsha="lahiri")["meta"]["house_system"] == "whole_sign"
    assert cusps(chart()) == cusps(chart(house_system="placidus"))


@pytest.mark.parametrize("hs", ["placidus", "koch", "sripati", "equal", "whole_sign"])
def test_each_system_keeps_the_ascendant(hs):
    base, c = chart(), chart(house_system=hs)
    assert c["meta"]["house_system"] == hs
    assert c["lagna"]["ascendant"] == pytest.approx(base["lagna"]["ascendant"])
    assert len(c["houses"]) == 12


def test_shapes_of_the_systems():
    asc = chart()["lagna"]["ascendant"]
    eq = cusps(chart(house_system="equal"))
    assert [round((x - eq[0]) % 360, 6) for x in eq] == [30.0 * i for i in range(12)]
    assert eq[0] == pytest.approx(asc)
    ws = cusps(chart(house_system="whole_sign"))
    assert all(x % 30 == pytest.approx(0) for x in ws)
    assert cusps(chart(house_system="sripati")) != cusps(chart(house_system="placidus"))


def test_lahiri_can_choose_placidus():
    assert chart(ayanamsha="lahiri", house_system="placidus")["meta"]["house_system"] == "placidus"


def test_unknown_system_is_rejected():
    assert client.post("/chart", json={**BIRTH, "house_system": "regiomontanus"}).status_code == 422
