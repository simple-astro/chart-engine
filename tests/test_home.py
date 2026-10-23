"""The homepage: what signed-out visitors see at /, and anyone at /home."""
import pytest
from fastapi.testclient import TestClient

from app import access
from app.main import app


@pytest.fixture
def gated(tmp_path, monkeypatch):
    monkeypatch.setenv("CHART_DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setenv("TESTER_ACCESS_CODES", "tester-code")
    monkeypatch.setenv("ADMIN_ACCESS_CODE", "admin-code")
    access._fails.clear()
    yield
    access._fails.clear()


def test_signed_out_visitors_get_the_homepage(gated):
    page = TestClient(app).get("/").text
    assert "Simple guidance, backed by precise Jyotish." in page
    assert 'action="/login"' in page and 'name="code"' in page      # the access-code form opens from the buttons
    assert "{{TODAY}}" not in page and "Today in India" in page      # today's tithi and nakshatra, filled in
    assert "{{PDAY}}" not in page and 'data-share="whatsapp"' in page and "/panchang/" in page   # today's panchang to share


def test_signed_in_users_still_get_the_app(gated):
    c = TestClient(app)
    c.post("/login", data={"code": "tester-code"}, follow_redirects=False)
    assert "Simple guidance, backed by precise Jyotish." not in c.get("/").text


def test_home_is_public_for_review(gated):
    assert TestClient(app).get("/home").status_code == 200


def test_sign_in_from_the_homepage_works(gated):
    c = TestClient(app)
    r = c.post("/login", data={"code": "tester-code"}, follow_redirects=False)
    assert r.status_code == 303 and c.get("/profiles").status_code == 200


def test_today_chip_names_tithi_and_nakshatra():
    chip = access.today_chip()
    assert chip.startswith("Today in India · ") and chip.count("·") == 2


def test_homepage_wording_rules():
    page = access.home_page()
    for banned in ("Generic AI", "Built by astrologers, for astrologers", "One app."):  # not a competitor's wording
        assert banned not in page
    assert "Founded by Astropositivism Team" in page and "Sukhdeep" not in page
