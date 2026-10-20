"""Prashna time bar: KP and Jamakkol charts can be recast for another day or time, without saving anything."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TOOLS = (Path(__file__).resolve().parent.parent / "app" / "static" / "tools.js").read_text()
WHEN = datetime(2026, 10, 20, 0, 43, tzinfo=timezone.utc)


def test_kp_horary_follows_the_chosen_time():
    body = {"number": 77, "kind": "job", "lat": 30.7363, "lon": 76.7884}
    kinds = [k["kind"] for k in client.get("/horary/kinds").json()]
    body["kind"] = kinds[0]
    a = client.post("/horary", json={**body, "asked_at": WHEN.isoformat()}).json()
    b = client.post("/horary", json={**body, "asked_at": (WHEN + timedelta(days=1)).isoformat()}).json()
    assert a["asked_at"].startswith("2026-10-20T00:43") and b["asked_at"].startswith("2026-10-21T00:43")
    assert a["chart"]["planets"]["Moon"] != b["chart"]["planets"]["Moon"]


def test_jamakkol_follows_the_chosen_time():
    kind = client.get("/jamakkol/kinds").json()[0]["kind"]
    body = {"kind": kind, "lat": 30.7363, "lon": 76.7884, "tz_name": "Asia/Kolkata"}
    a = client.post("/jamakkol", json={**body, "asked_at": WHEN.isoformat()}).json()
    b = client.post("/jamakkol", json={**body, "asked_at": (WHEN + timedelta(hours=4)).isoformat()}).json()
    assert a["asked_at"] != b["asked_at"]
    assert a["reading"]["question"]["kind"] == kind


def test_time_bar_in_the_page():
    assert "function timeBar(" in TOOLS and 'max="1439"' in TOOLS
    # both tools recast through the plain endpoints, so a saved Jamakkol question is never changed
    assert "post('/horary', { ...body, asked_at: at })" in TOOLS
    assert "post('/jamakkol', { kind: g.question.kind" in TOOLS
    assert 'class="tbar lv-pro"' in TOOLS  # astrologers' level only
