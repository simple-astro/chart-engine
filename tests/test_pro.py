"""Pro dashboard: the extra tables (avasthas, friendships, Vimshopaka, upagrahas, Sade Sati), who may open /pro,
and the saved layout."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app
from core import pro_tables as T

BIRTH = {"name": "Pro Test", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.7363, "lon": 76.7884,
         "tz_name": "Asia/Kolkata", "ayanamsha": "krishnamurti"}


@pytest.fixture(scope="module")
def chart():
    from app.routes import with_extras
    return with_extras(TestClient(app).post("/chart", json=BIRTH).json())


def test_baladi_runs_backwards_in_even_signs():
    assert T.baladi(0, 2) == "Bala (infant)" and T.baladi(0, 29) == "Mrita (dead)"      # Aries, an odd sign
    assert T.baladi(1, 2) == "Mrita (dead)" and T.baladi(1, 29) == "Bala (infant)"      # Taurus, an even sign


def test_jagradadi_follows_dignity():
    assert T.jagradadi("Sun", 4) == "Jagrat (awake)"        # own sign Leo
    assert T.jagradadi("Moon", 7) == "Sushupti (asleep)"    # debilitated in Scorpio
    assert T.jagradadi("Jupiter", 4) == "Swapna (dreaming)"  # a friend's sign


def test_friendship_tables(chart):
    f = T.friendship(chart)
    assert f["natural"]["Sun"]["Moon"] == "Friend" and f["natural"]["Sun"]["Venus"] == "Enemy"
    assert f["temporary"]["Sun"]["Mercury"] == "Enemy"       # same sign is not a temporary friend
    assert f["fivefold"]["Sun"]["Moon"] == "Great friend"    # natural friend, 4th from the Sun


def test_vimshopaka_is_out_of_twenty(chart):
    v = T.vimshopaka(chart)
    for p in T.P:
        for scheme, score in v[p].items():
            assert 5 * sum(T.SCHEMES[scheme].values()) / 20 <= score <= 20, (p, scheme, score)
    assert all(abs(sum(w.values()) - 20) < 1e-9 for w in T.SCHEMES.values())


def test_upagrahas_follow_the_sun(chart):
    u = {x["name"]: x["longitude"] for x in T.upagrahas(chart)}
    sun = chart["grahas"]["Sun"]["longitude"]
    assert u["Dhuma"] == pytest.approx((sun + 133 + 1 / 3) % 360, abs=1e-3)
    assert u["Upaketu"] == pytest.approx((sun - 30) % 360, abs=1e-3)  # the five add up to Sun − 30°


def test_sade_sati_episodes(chart):
    s = T.sade_sati(chart)
    starts = [e["start"][:4] for e in s["episodes"]]
    assert starts[:3] == ["1987", "2011", "2041"]           # Moon in Scorpio: born in one, then 2011 and 2041
    assert s["episodes"][0]["from_birth"] and s["episodes"][0]["phases"][0]["phase"] == "Peak"
    assert all(e["phases"] and e["start"] <= e["end"] for e in s["episodes"])
    assert {d["kind"] for d in s["dhaiyas"]} == {"Kantaka (4th)", "Ashtama (8th)"}


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def _login(code, nxt="/"):
    c = TestClient(app)
    assert c.post("/login", data={"code": code, "next": nxt}, follow_redirects=False).status_code == 303
    return c


def test_who_may_open_pro(gated):
    assert "Pro dashboard sign-in" in TestClient(app).get("/pro").text         # signed out: the sign-in page
    t = _login("tester-code")
    assert t.get("/pro", follow_redirects=False).status_code == 303           # testers keep the everyday app
    assert t.put("/pro/api/layout", json={"widgets": []}).status_code == 403
    owner = _login("admin-code", "/admin")
    astro = owner.post("/admin/api/team", json={"label": "Mentor", "role": "mentor"}).json()
    m = _login(astro["code"], "/pro")
    assert "SIMPLEJYOTISH · PRO" in m.get("/pro").text
    pid = m.post("/profiles", json=BIRTH).json()["id"]
    tables = m.get(f"/pro/api/tables/{pid}").json()
    assert set(tables) == {"avastha", "friendship", "vimshopaka", "upagrahas", "sade_sati"}


def test_tester_code_cannot_sign_in_to_pro(gated):
    r = TestClient(app).post("/login", data={"code": "tester-code", "next": "/pro"}, follow_redirects=False)
    assert r.status_code == 401 and "Pro dashboard needs" in r.text


def test_layout_is_saved_and_checked(gated):
    owner = _login("admin-code", "/admin")
    assert owner.put("/pro/api/layout", json={"widgets": [{"id": "d1", "w": 1}, {"id": "spasht", "w": 2}]}).status_code == 200
    assert owner.get("/pro/api/layout").json()["widgets"] == [{"id": "d1", "w": 1}, {"id": "spasht", "w": 2}]
    assert owner.put("/pro/api/layout", json={"widgets": [{"id": "d1", "w": 9}]}).status_code == 422


def test_widget_library_covers_every_module():
    js = (Path(__file__).resolve().parent.parent / "app" / "static" / "pro.js").read_text()
    for wid in ("panchang", "moonq", "d1", "d9", "chalit", "moonchart", "sunchart", "vall", "spasht", "retro", "baladi",
                "jagrad", "d1sav", "fnat", "ftat", "fpan", "karakas", "vimsho", "vargottam", "special", "upagraha", "sav", "dnow",
                "dlist", "sbt", "sbsthana", "sbkala", "sbchesta", "sbdig", "sbdrik", "sbnais", "sbik", "bhavab", "drishti", "d1asp", "lordx",
                "ynow", "ylist", "chara", "narayana", "arudha", "ssnow", "ssep", "ssdh", "gtime", "gchart", "gpos",
                "gbasic", "nlagdeg", "ncusp", "nsig3", "nplanet", "nprime", "nrevolve", "naspp", "naspc", "ndasha", "nrp2", "ntime", "kpcusp", "kpsigh", "kpsigp", "ruling", "yogas", "kpwin", "bnn", "nadi", "lalkitab", "tajika"):
        assert f"add('{wid}'" in js, wid


def test_nadi_grid_event_houses():
    js = (Path(__file__).resolve().parent.parent / "app" / "static" / "pro.js").read_text()
    for row in ("['marriage', 'Marriage', [2, 7, 11], [1, 6, 10]]", "['divorce', 'Divorce / separation', [1, 6, 10], [2, 7, 11]]",
                "'Love affair (5, 9, 11 or 5, 8, 11)', [5, 8, 9, 11]", "['career', 'Job / promotion', [2, 6, 10, 11], [5, 9]]"):
        assert row in js, row


def test_auto_arrange_and_reset_controls():
    root = Path(__file__).resolve().parent.parent / "app" / "static"
    html, js = (root / "pro.html").read_text(), (root / "pro.js").read_text()
    assert 'id="autoarr"' in html and 'id="resetdef"' in html
    assert "function autoArrange()" in js and "target.w += 1; room--" in js  # rows always end flush
    assert "function resetDefault()" in js and "fromPreset('parashari')" in js
