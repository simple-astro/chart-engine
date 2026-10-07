"""Regression guard: dated events from the book's illustrations should fall in windows the engine rates
favourable or strong. Each event is tied to the DBA the book states (several book dates are month-only)."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import kp_predict as K

DELHI = (28.6667, 77.2167)
EVENTS = [  # label, dob, tob, place, topic, approx date (None = book gives only the DBA), book's DBA
    ("H1 engagement fixed", "1950-06-07", "22:30", DELHI, "marriage", "1978-12-04", "Mercury-Mercury-Ketu"),
    ("H1 marriage", "1950-06-07", "22:30", DELHI, "marriage", "1979-06-29", "Mercury-Mercury-Sun"),
    ("H1 house bought", "1950-06-07", "22:30", DELHI, "property", "1986-03-10", "Mercury-Moon-Saturn"),
    ("H1 commercial property", "1950-06-07", "22:30", DELHI, "property", "1994-05-25", "Mercury-Saturn-Moon"),
    ("H1 property sold", "1950-06-07", "22:30", DELHI, "property_sale", "1994-05-13", "Mercury-Saturn-Moon"),
    ("H1 car bought", "1950-06-07", "22:30", DELHI, "vehicle", "1995-06-03", "Ketu-Ketu-Venus"),
    ("H1 second car", "1950-06-07", "22:30", DELHI, "vehicle", "1995-12-13", "Ketu-Venus-Venus"),
    ("H1 won court case", "1950-06-07", "22:30", DELHI, "litigation_win", "1997-10-15", "Ketu-Moon-Ketu"),
    ("H2 marriage", "1952-08-26", "05:30", DELHI, "marriage", "1982-04-15", "Jupiter-Rahu-Venus"),
    ("CH9A engagement", "1979-01-17", "12:26", (25.18, 75.83), "marriage", "2000-07-02", "Sun-Venus-Mercury"),
    ("CH9B marriage fixed", "1980-01-15", "00:10", DELHI, "marriage", "2002-02-17", "Venus-Venus-Saturn"),
    ("CH9H marriage", "1958-01-11", "18:30", DELHI, "marriage", "1982-11-15", "Rahu-Ketu-Mars"),
    ("CH8F job change", "1978-09-11", "11:00", (18.52, 73.86), "job_change", "2008-08-13", "Moon-Rahu-Jupiter"),
    ("CH8H joined police", "1970-06-06", "08:00", DELHI, "career", None, "Jupiter-Mars-Sun"),
    ("CH8M joined army", "1979-11-24", "02:45", (30.73, 76.78), "career", None, "Mars-Jupiter-Moon"),
    ("CH10A conceived", "1971-05-14", "22:20", DELHI, "children", "1998-02-15", "Mars-Rahu-Venus"),
    ("CH6E appendix surgery", "1971-02-10", "10:54", DELHI, "illness", "1978-07-20", "Ketu-Mars-Sun"),
]


def verdict_at_book_dba(c, topic, dob, when, dba):
    book = dba.split("-")
    lo, hi = (date.fromisoformat(dob) + timedelta(days=16 * 365), date(2060, 1, 1)) if when is None else \
             (date.fromisoformat(when) - timedelta(days=75), date.fromisoformat(when) + timedelta(days=75))
    per = next(p for p in K.periods_in(c, lo, hi) if [p["maha"], p["antar"], p["praty"]] == book)
    mid = per["starts"] + (per["ends"] - per["starts"]) / 2
    return next(w for w in K.predict(c, topic, mid - timedelta(days=1), months=1)["windows"]
                if w["starts"] <= mid.isoformat() < w["ends"])["verdict"]


@pytest.fixture(scope="module")
def verdicts():
    cl = TestClient(app)
    out = {}
    for label, dob, tob, (lat, lon), topic, when, dba in EVENTS:
        c = cl.post("/chart", json={"dob": dob, "tob": tob + ":00", "lat": lat, "lon": lon, "tz_name": "Asia/Kolkata"}).json()
        out[label] = verdict_at_book_dba(c, topic, dob, when, dba)
    return out


def test_book_events_fall_in_favourable_windows(verdicts):
    hits = [l for l, v in verdicts.items() if v in ("strong", "favourable")]
    assert len(hits) >= 14, f"only {len(hits)}/{len(verdicts)}: misses {set(verdicts) - set(hits)}"
    assert sum(v == "strong" for v in verdicts.values()) >= 10


def test_dasha_balance_matches_the_book():
    c = TestClient(app).post("/chart", json={"dob": "1950-06-07", "tob": "22:30:00", "lat": 28.6667, "lon": 77.2167,
                                             "tz_name": "Asia/Kolkata"}).json()
    first = c["dasha"][0]
    assert first["lord"] == "Jupiter" and first["end"][:10] in ("1959-05-22", "1959-05-23")  # book: Jup 8y 11m 15d
