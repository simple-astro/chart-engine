"""Fact check: period start dates, today's weekday and date, and the place clock times are for."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import chat, factcheck, synthesis
from app.main import app
from app.routes import with_extras

REQ = {"dob": "1987-09-01", "tob": "14:20:00", "lat": 30.7333, "lon": 76.7794, "tz_name": "Asia/Kolkata",
       "place": "Chandigarh, India"}


@pytest.fixture(scope="module")
def facts():
    c = with_extras(TestClient(app).post("/chart", json={**REQ, "ayanamsha": "pushya"}).json())
    now = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)  # Sunday 18 October in India
    return factcheck.facts_from(synthesis.build({"chart": c, "request": REQ}, now), c)


@pytest.mark.parametrize("text, wrong", [
    ("Your Venus mahadasha began in August 2010.", True),
    ("Your Venus mahadasha began in April 2009.", False),
    ("Today is Saturday, October 19.", True),
    ("Today, Sunday, keep to routine work.", False),
    ("Tomorrow, 20 October, is better.", True),
    ("Tomorrow is Monday, Oct 19.", False),
    ("Here are your Winnipeg times: Rahu Kalam 7:52 to 9:17 AM.", True),
    ("Chandigarh times for Monday: Rahu Kalam 7:52–9:17 AM.", False),
    ("Winnipeg's sunrise and Rahu Kalam fall at different clock times.", False),
])
def test_claims(facts, text, wrong):
    assert bool(factcheck.check(text, facts)) is wrong


def test_the_ai_is_told_today_and_the_place_its_times_are_for():
    p = {"request": REQ, "viewer": {"lat": 49.9, "lon": -97.1, "tz_name": "America/Winnipeg", "name": "Winnipeg"},
         "channel": "telegram"}
    line = chat._now_line(p)
    assert "Winnipeg (America/Winnipeg)" in line and "Where I live" in line and "today is" in line
