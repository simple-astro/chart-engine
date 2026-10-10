"""Remedy knowledge base: content rules, import/review/approve, and serving only approved items."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.remedies import library
from app.remedies.schema import Invalid, validate

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "remedies_fixture.json").read_text())["items"]
# The curated library lives in the private repo; validate it too when it is checked out next to this one.
PRIVATE = Path(os.environ.get("REMEDY_SEED", Path(__file__).resolve().parents[2] / "jyotish-platform" /
                              "content" / "remedies" / "remedies_seed.yaml"))


def _remedy(**k):
    base = {"slug": "x-test", "planet": "Saturn", "type": "seva", "source": "lal_kitab", "intent": ["pacify"],
            "cost_tier": "free", "effort": 1, "title": "Serve", "steps": ["Help someone."], "why_template": "w"}
    return {**base, **k}


@pytest.mark.parametrize("item,err", [
    (_remedy(type="jal_pravah"), "diaspora_alternative"),
    (_remedy(type="vrat", safety_notes=["Not in pregnancy."]), "light_variant"),
    (_remedy(type="ratna", intent=["strengthen"], substitute="Amethyst"), "requires_advisor_review"),
    (_remedy(type="ratna", intent=["pacify"], substitute="Amethyst", requires_advisor_review=True), "never be a pacify"),
    (_remedy(steps=["Keep a piece of ivory at home."]), "banned material"),
    (_remedy(steps=["Wear a deer skin on Saturdays."]), "banned material"),
    (_remedy(why_template="Otherwise you will face poverty."), "fear wording"),
    (_remedy(intent="pacify"), "intent must be a list"),
    (_remedy(effort=9), "effort"),
    (_remedy(slug="Bad Slug"), "slug"),
    (_remedy(timing={"duration_days": 30}), "duration_days"),
])
def test_content_rules(item, err):
    with pytest.raises(Invalid, match=err):
        validate("remedy", item)


def test_good_items_pass_and_gems_need_substitutes():
    for it in FIXTURE:
        validate(it["kind"], {k: v for k, v in it.items() if k != "kind"})
    validate("remedy", _remedy(type="jal_pravah", diaspora_alternative="Give it at a temple instead."))
    validate("remedy", _remedy(type="ratna", intent=["strengthen"], substitute="Amethyst", requires_advisor_review=True))
    with pytest.raises(Invalid, match="substitute"):
        validate("graha", {"planet": "Sun", "colors": ["red"], "beej_mantra": "m", "japa_count": 7000, "gem": "Ruby"})
    with pytest.raises(Invalid, match="blocks"):
        validate("rule", {"slug": "r-x", "planet": "Moon", "when": {"house": 6}, "blocks": {}, "reason": "r"})


@pytest.mark.skipif(not PRIVATE.exists(), reason="private remedy seed not checked out")
def test_private_seed_passes_every_content_rule():
    import yaml
    items = yaml.safe_load(PRIVATE.read_text())["items"]
    for it in items:
        validate(it["kind"], {k: v for k, v in it.items() if k != "kind"})
    kinds = {it["kind"] for it in items}
    assert kinds == {"graha", "remedy", "rule", "rin", "home_audit"}
    assert {it["planet"] for it in items if it["kind"] == "graha"} == {
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
    assert all(it.get("review_status", "pending_astrologer") == "pending_astrologer" for it in items)


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)


def _client(code):
    c = TestClient(app)
    c.post("/login", data={"code": code, **({"next": "/admin"} if code == "admin-code" else {})},
           follow_redirects=False)
    return c


def test_import_review_approve_and_serve(gated):
    a = _client("admin-code")
    r = a.post("/admin/api/remedies/import", json={"items": FIXTURE})
    assert r.status_code == 200 and r.json() == {"added": 6, "updated": 0, "unchanged": 0}
    assert a.post("/admin/api/remedies/import", json={"items": FIXTURE}).json() == {"added": 0, "updated": 0, "unchanged": 6}
    # nothing is served in production until approved
    assert library.served("remedy") == []
    assert a.patch("/admin/api/remedies/remedy/sun-arghya", json={"review_status": "approved"}).status_code == 200
    assert [i["slug"] for i in library.served("remedy")] == ["sun-arghya"]
    # editing content sends it back for review and bumps the version
    item = a.get("/admin/api/remedies?kind=remedy").json()["items"][0]
    data = {k: v for k, v in item.items() if k not in ("kind", "slug", "review_status", "version", "updated_at")}
    r = a.patch("/admin/api/remedies/remedy/sun-arghya", json={"data": {**data, "effort": 2}})
    assert r.status_code == 200 and r.json()["review_status"] == "pending_astrologer" and r.json()["version"] == 2
    assert library.served("remedy") == []
    # invalid edits and imports are refused whole, with the reason
    r = a.patch("/admin/api/remedies/remedy/sun-arghya", json={"data": {**data, "steps": ["Use ivory."]}})
    assert r.status_code == 422 and "banned" in r.json()["detail"]
    r = a.post("/admin/api/remedies/import", json={"text": "items:\n  - kind: remedy\n    slug: bad\n"})
    assert r.status_code == 422 and "item 1" in r.json()["detail"]
    assert a.get("/admin/api/remedies").json()["counts"]["remedy"]["pending_astrologer"] == 2
    exp = a.get("/admin/api/remedies/export").json()["items"]
    assert len(exp) == 6 and all("version" not in i for i in exp)
    # admin only
    t = _client("tester-code")
    assert t.get("/admin/api/remedies").status_code == 403
    assert t.post("/admin/api/remedies/import", json={"items": FIXTURE}).status_code == 403


def test_local_mode_previews_pending_content(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    for k in ("ADMIN_ACCESS_CODE", "TESTER_ACCESS_CODES"):
        monkeypatch.delenv(k, raising=False)
    library.import_items(FIXTURE)
    assert {i["slug"] for i in library.served("remedy")} == {"sun-arghya", "sun-wheat-daan"}
