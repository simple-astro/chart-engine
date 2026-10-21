from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

from core import sarvatobhadra as S


def _naks(cells):
    return {S.NAK28[S.GRID[r][c][1]] for r, c in cells if S.GRID[r][c][0] == "n"}


def test_grid_holds_every_element_once():
    kinds = Counter(cell[0] for row in S.GRID for cell in row)
    assert kinds == {"n": 28, "v": 16, "c": 20, "s": 12, "t": 5}
    assert len(S.WHERE) == 81
    border = [S.GRID[0][1:8], [S.GRID[r][8] for r in range(1, 8)], S.GRID[8][7:0:-1], [S.GRID[r][0] for r in range(7, 0, -1)]]
    order = [cell[1] for side in border for cell in side]
    assert order[:4] == [22, 23, 24, 25] and order[7:10] == [2, 3, 4]  # Krittika opens the east side
    assert order[-7:] == [16, 17, 18, 19, 20, S.ABHIJIT, 21]           # Abhijit sits between Uttarashadha and Shravana


def test_krittika_strikes_shravana_bharani_and_vishakha():
    ln = S.lines(2)
    assert _naks(ln["front"]) == {"Shravana"}
    assert _naks(ln["diagonal_1"] + ln["diagonal_-1"]) == {"Bharani", "Vishakha"}
    front = {S.label(S.GRID[r][c]) for r, c in ln["front"]}
    assert {"च cha", "ल la", "द da", "स sa", "ग ga"} <= front


def test_every_nakshatra_front_line_reaches_the_opposite_side():
    for k in range(28):
        assert len(_naks(S.lines(k)["front"])) == 1


def test_abhijit_span():
    assert S.nak28(276.0) == 20 and S.nak28(277.0) == S.ABHIJIT and S.nak28(281.0) == 21


def test_strikes_and_corner_vowel():
    hit = S.strikes({"Jupiter": (25.0, False)})  # last pada of Bharani: also strikes the NE corner vowel a
    assert any(s["line"] == "corner" for s in hit[(0, 8)])
    assert all(s["nature"] == "benefic" for v in hit.values() for s in v)
    assert hit[S.WHERE[("n", 1)]][0]["line"] == "in"


def test_market_signals():
    rows = S.market(datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata")), {2: "gold, silver"})
    assert len(rows) == 28 and rows[2]["goods"] == "gold, silver"
    for r in rows:
        want = ("teji" if r["malefic"] and not r["benefic"] else "mandi" if r["benefic"] and not r["malefic"]
                else "mixed" if r["benefic"] else "quiet")
        assert r["signal"] == want


def test_money_days_are_explained():
    pts = S.natal_points(moon_lon=227.6, sun_lon=135.0, lagna_sign=8, weekday="Tuesday")
    assert pts["2nd house (wealth)"] == S.WHERE[("s", 9)] and pts["11th house (gains)"] == S.WHERE[("s", 6)]
    days = S.money_days(pts, date(2026, 11, 1), 7, "Asia/Kolkata")
    assert len(days) == 7
    for d in days:
        assert d["score"] == d["moon"] + d["backdrop"]
        assert d["verdict"] != "good" or d["moon"] > 0
        assert len({(w["point"], w["planet"]) for w in d["why"]}) == len(d["why"])  # each planet once per point


def test_points_sharing_a_box_count_once():
    pts = S.natal_points(moon_lon=215.0, sun_lon=100.0, lagna_sign=7, weekday="Monday")  # Moon sign = lagna = Scorpio
    assert pts["Moon sign"] == pts["Lagna"]
    d = S.money_day(pts, {"Venus": (215.0, False)})
    assert sum(1 for w in d["why"] if "Lagna" in w["point"]) == 1


def test_waning_moon_is_malefic():
    assert S.nature("Moon", {"Moon": (100.0, False), "Sun": (10.0, False)}) == "benefic"
    assert S.nature("Moon", {"Moon": (10.0, False), "Sun": (100.0, False)}) == "malefic"


def _client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    return TestClient(app)


BIRTH = {"name": "A", "dob": "1990-05-15", "tob": "14:30:00", "lat": 28.6139, "lon": 77.209, "tz_name": "Asia/Kolkata"}


def test_api_personal_chakra_and_market(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/sarvatobhadra", json={"birth": BIRTH, "start": "2026-11-01", "days": 7, "tz_name": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["grid"]) == 9 and len(d["money_days"]) == 7 and "Birth nakshatra" in d["points"]
    assert sum(len(cell["marks"]) for row in d["grid"] for cell in row) == len(d["points"])
    m = c.get("/sarvatobhadra/market", params={"on": "2026-11-01", "tz_name": "Asia/Kolkata"}).json()
    assert len(m["rows"]) == 28 and m["has_goods"] is False


def test_api_panchapakshi(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/panchapakshi", json={"birth": BIRTH, "date": "2026-11-01", "days": 2, "lat": 28.6356,
                                      "lon": 77.2244, "tz_name": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["bird"] in ("Vulture", "Owl", "Crow", "Cock", "Peacock") and len(d["days"]) == 2
    assert len(d["days"][0]["yamas"]) == 10 and d["days"][0]["paksha"] == "Krishna"
    assert c.post("/panchapakshi", json={"birth": BIRTH, "date": "2026-11-01", "days": 9, "lat": 0, "lon": 0,
                                         "tz_name": "Asia/Kolkata"}).status_code == 422
