"""The dark theme is warm ink (no purple), and the pages carry the iPhone settings."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import access
from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
OLD_PURPLE = ("#0a0812", "#120e1f", "#1b162b", "#b89bf5", "184,155,245", "#1a1322", "27,22,43")


def test_pages_have_no_purple_left():
    for name in ("index.html", "admin.html"):
        text = (STATIC / name).read_text()
        assert not [c for c in OLD_PURPLE if c in text], name
    assert not [c for c in OLD_PURPLE if c in Path(access.__file__).read_text()]


def test_iphone_settings_are_present():
    for name in ("index.html", "admin.html"):
        text = (STATIC / name).read_text()
        assert "viewport-fit=cover" in text and 'name="theme-color"' in text, name
    index = (STATIC / "index.html").read_text()
    assert "-apple-system" in index.split("--sans:")[1][:80] and "input,select,textarea{font-size:16px!important}" in index


def test_sign_in_page_matches_the_theme(monkeypatch):
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    r = TestClient(app).get("/login")
    assert "viewport-fit=cover" in r.text and "#0a0907" in r.text and "#0a0812" not in r.text
