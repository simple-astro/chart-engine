"""AI-polished Varshaphal wording (app/varshaphal_polish.py): the fact guard keeps the rules' line whenever the AI adds
a planet, house, sign, date or certainty word; good rewrites pass; results are cached."""
import json
from types import SimpleNamespace

from app import chat, varshaphal as V, varshaphal_polish as VP
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import tajika

REQ = {"name": "t", "dob": "1988-08-12", "tob": "07:40:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata"}


def _reading():
    req = ChartRequest(**REQ)
    c = compute_chart(req)
    return V.reading(c, tajika.annual(c, req.model_dump(mode="json"), 38))


def test_guard():
    src = "Work holds steady; gains come slowly. 10th lord Saturn in the 11th, retrograde"
    assert VP.guard("Work stays steady, and gains build slowly with patience.", src) is None
    assert VP.guard("Saturn in your 11th keeps work slow until March 2027.", src) == "added 2027, march"
    assert VP.guard("Jupiter will bless your work.", src).startswith("added jupiter")
    assert VP.guard("You will definitely be promoted.", src) == "certainty or fear wording"
    assert VP.guard("", src) == "empty"


def test_polish_keeps_rules_where_the_ai_adds_facts(monkeypatch):
    r = _reading()
    calls = []
    reply = {"headline": "This year asks for steady effort and care for yourself; talks, courses and short trips shine.",
             "areas": {a["key"]: f"Polished {a['label'].lower()}." for a in r["areas"]},
             "dasha": "Your Sun period has just begun and the year backs it.",
             "months": [f"Polished month {i}." for i in range(len(r["months"]))]}
    reply["areas"]["work"] = "Mercury brings a promotion in the 10th house."   # adds facts: refused

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(reply))],
                               usage=SimpleNamespace(input_tokens=900, output_tokens=300))
    monkeypatch.setattr(chat, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=create)))
    VP._CACHE.clear()
    out, use = VP.polish(r, "1|38", "claude-haiku-4-5")
    work = next(a for a in r["areas"] if a["key"] == "work")
    assert out["areas"]["work"] == work["text"] and out["kept"][0]["field"] == "Work"
    assert out["areas"]["money"] == "Polished money." and out["months"][0] == "Polished month 0."
    assert out["dasha"].startswith("Your Sun period") and use["input"] == 900
    again, use2 = VP.polish(r, "1|38", "claude-haiku-4-5")
    assert again == out and use2 is None and len(calls) == 1  # served from the cache


def test_admin_setting_turns_it_off(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import config
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    c = TestClient(app)
    pid = c.post("/profiles", json=REQ).json()["id"]
    config.update({"varshaphal_ai": "off"})
    assert c.get(f"/profiles/{pid}/tajika/polish?years=38").status_code == 403
    assert c.get("/me").json()["varshaphal_ai"] == "off"


def test_only_the_admin_gets_it_while_comparing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import config
    from app.main import app
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    t = TestClient(app)
    t.post("/login", data={"code": "tester-code"}, follow_redirects=False)
    pid = t.post("/profiles", json=REQ).json()["id"]
    config.update({"varshaphal_ai": "studio"})
    assert t.get(f"/profiles/{pid}/tajika/polish?years=38").status_code == 403
    assert t.get("/me").json()["admin"] is False  # the app hides the switch from this
