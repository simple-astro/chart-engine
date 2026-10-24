"""Gender (male or female) is an optional chart input, kept with the saved chart."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

INDEX = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text()
REQ = {"name": "G", "place": "Delhi", "dob": "1990-05-15", "tob": "08:30:00", "lat": 28.61, "lon": 77.21,
       "tz_name": "Asia/Kolkata", "ayanamsha": "lahiri"}


def test_gender_is_optional_and_only_male_or_female():
    c = TestClient(app)
    assert c.post("/chart", json=REQ).status_code == 200                       # old requests still work
    assert c.post("/chart", json={**REQ, "gender": "female"}).status_code == 200
    assert c.post("/chart", json={**REQ, "gender": "other"}).status_code == 422


def test_gender_is_saved_with_the_profile():
    c = TestClient(app)
    p = c.post("/profiles", json={**REQ, "gender": "male"}).json()
    try:
        assert c.get(f"/profiles/{p['id']}").json()["request"]["gender"] == "male"
    finally:
        c.delete(f"/profiles/{p['id']}")


def test_form_asks_for_gender_and_sends_it():
    assert 'name="gender" value="male"' in INDEX and 'name="gender" value="female"' in INDEX
    assert "body.gender=gen.value" in INDEX and "r.checked=r.value===q.gender" in INDEX
