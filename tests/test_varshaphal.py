"""The Varshaphal reading by rules (app/varshaphal.py): the year's tone and theme, areas, the Dasha link, months, and
Life by years with the person's own events."""
from fastapi.testclient import TestClient

from app import varshaphal as V
from app.main import app
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import tajika

REQ = {"name": "t", "dob": "1988-08-12", "tob": "07:40:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata", "ayanamsha": "krishnamurti"}


def _year(years):
    req = ChartRequest(**REQ)
    c = compute_chart(req)
    return c, tajika.annual(c, req.model_dump(mode="json"), years)


def test_reading_for_a_sample_year():
    c, r = _year(38)  # Muntha in the 6th, Moon the year lord in its own sign, Jupiter exalted in the 3rd
    x = V.reading(c, r)
    assert x["tone"] == "steady" and x["headline"].startswith("Effort, health and routine.")
    areas = {a["key"]: a for a in x["areas"]}
    assert len(areas) == 7 and all(a["tone"] in ("go", "good", "steady", "care") and a["text"] for a in areas.values())
    assert areas["siblings"]["tone"] == "go" and "Jupiter exalted in the 3rd" in areas["siblings"]["why"]
    assert areas["health"]["tone"] == "care" and "Muntha in the 6th" in areas["health"]["why"]
    assert "Year lord: Moon, own sign" in x["chips"]


def test_dasha_link_and_key_stretch():
    c, r = _year(38)
    D = V.reading(c, r)["dasha"]
    assert D["maha"] == "Sun" and D["verdict"] in ("agrees", "softens", "neutral") and "began in October 2026" in D["text"]
    assert [k["lord"] for k in D["key"]] == ["Moon"] and D["key"][0]["start"].startswith("2027-01-18")


def test_months_follow_the_mudda_dasha():
    c, r = _year(38)
    ms = V.reading(c, r)["months"]
    assert [m["lord"] for m in ms] == [m["lord"] for m in r["mudda_dasha"]]
    assert next(m for m in ms if m["lord"] == "Moon")["year_lord"] and sum(1 for m in ms if m.get("best")) == 1
    assert all(m["text"].endswith(".") and m["text"].count(" and ") <= 2 for m in ms)


def test_life_by_years_places_events_and_checks_them():
    req = ChartRequest(**REQ)
    c = compute_chart(req)
    rows = V.life(c, req.model_dump(mode="json"), 40, [{"kind": "married", "date": "2020-11-10"},
                                                       {"kind": "loss", "date": "2022-01-05"}])
    assert len(rows) == 41 and rows[0]["years"] == 0 and rows[0]["year"] == 1988
    y32 = rows[32]
    assert y32["muntha_house"] == 7 and y32["events"][0]["fit"] and "Muntha in the 7th" in y32["events"][0]["why"]
    loss = rows[33]["events"][0]
    assert loss["checked"] is False and loss["fit"] is False  # never read against the chart


def test_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    d = c.get(f"/profiles/{pid}/tajika?years=38").json()
    assert d["reading"]["headline"] and len(d["reading"]["areas"]) == 7 and d["reading"]["months"]
    life = c.get(f"/profiles/{pid}/tajika/years").json()
    assert life["now"] >= 38 and len(life["years"]) == life["now"] + 11 and life["years"][38]["year"] == 2026
