import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core import panchapakshi as P

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DELHI = (28.6356, 77.2244, "Asia/Kolkata")
IST = ZoneInfo("Asia/Kolkata")


def test_shukla_tables_match_pulippani_page_48():
    ref = json.loads((Path(__file__).parent / "fixtures" / "panchapakshi_shukla_pulippani.json").read_text())
    for half, key in (("day", "Day"), ("night", "Night")):
        for wd, d in enumerate(DAYS):
            for y in range(1, 6):
                for b in P.BIRDS:
                    assert P.activity("Shukla", half, wd, y, b) == ref[key][d][str(y)][b], (half, d, y, b)


# Drik Panchang, New Delhi, Krishna paksha 1–7 Nov 2026: the Vulture's five day and five night activities.
DRIK_KRISHNA_VULTURE = {
    "Sunday": ("WEDSR", "ESWDR"), "Monday": ("SRWED", "DREsW"), "Tuesday": ("WEDSR", "ESWDR"),
    "Wednesday": ("DSRWE", "SWDRE"), "Thursday": ("RWEDS", "WDRES"), "Friday": ("EDSRW", "RESWD"),
    "Saturday": ("SRWED", "DREsW"),
}
LETTER = {"R": "Ruling", "E": "Eating", "W": "Walking", "S": "Sleeping", "D": "Dying", "s": "Sleeping"}


@pytest.mark.parametrize("weekday", DAYS)
def test_krishna_vulture_matches_drik(weekday):
    wd = DAYS.index(weekday)
    for half, letters in zip(("day", "night"), DRIK_KRISHNA_VULTURE[weekday]):
        assert [P.activity("Krishna", half, wd, y, "Vulture") for y in range(1, 6)] == [LETTER[c] for c in letters]


def test_krishna_sunday_all_birds_match_drik():
    drik = {"Owl": ("DSRWE", "RESWD"), "Crow": ("RWEDS", "DRESW"), "Cock": ("EDSRW", "WDREs"),
            "Peacock": ("SRWED", "SWDRE")}
    for bird, (day, night) in drik.items():
        assert [P.activity("Krishna", "day", 0, y, bird) for y in range(1, 6)] == [LETTER[c] for c in day]
        assert [P.activity("Krishna", "night", 0, y, bird) for y in range(1, 6)] == [LETTER[c] for c in night]


def test_every_yama_gives_each_bird_a_different_activity():
    for (paksha, half) in P.TABLES:
        for wd in range(7):
            for y in range(1, 6):
                assert sorted(P.activity(paksha, half, wd, y, b) for b in P.BIRDS) == sorted(P.ACTS)


def test_birth_bird_tables():
    assert P.birth_bird(0, "Shukla") == "Vulture" and P.birth_bird(0, "Krishna") == "Peacock"
    assert P.birth_bird(9, "Shukla") == "Owl" and P.birth_bird(10, "Shukla") == "Crow"
    assert P.birth_bird(26, "Shukla") == "Peacock" and P.birth_bird(26, "Krishna") == "Vulture"
    assert P.birth_bird(21, "Krishna") == "Owl" and P.birth_bird(22, "Krishna") == "Vulture"
    assert P.paksha_of(10.0, 100.0) == "Shukla" and P.paksha_of(100.0, 10.0) == "Krishna"


def _hm(dt):
    return dt.astimezone(IST).hour * 60 + dt.astimezone(IST).minute


def test_vulture_day_plan_matches_drik_clock_times():
    plan = P.day_plan(date(2026, 11, 1), *DELHI, "Vulture")
    assert plan["paksha"] == "Krishna" and plan["weekday"] == "Sunday"
    starts = ["06:33", "08:46", "10:58", "13:11", "15:23", "17:36", "20:12", "22:47", "01:23", "03:58"]
    for y, s in zip(plan["yamas"], starts):
        h, m = map(int, s.split(":"))
        assert abs(_hm(y["start"]) - (h * 60 + m)) <= 2, (y["half"], y["yama"])
    d1 = plan["yamas"][0]["subs"]
    assert [(s["bird"], s["activity"]) for s in d1] == [("Vulture", "Walking"), ("Cock", "Eating"), ("Owl", "Dying"),
                                                        ("Peacock", "Sleeping"), ("Crow", "Ruling")]
    for s, drik in zip(d1[1:], ["07:06", "07:50", "08:18", "08:29"]):
        h, m = map(int, drik.split(":"))
        assert abs(_hm(s["start"]) - (h * 60 + m)) <= 2
    n1 = plan["yamas"][5]["subs"]
    assert [(s["bird"], s["activity"]) for s in n1] == [("Vulture", "Eating"), ("Peacock", "Sleeping"),
                                                        ("Cock", "Walking"), ("Crow", "Dying"), ("Owl", "Ruling")]


def test_shukla_sub_period_lengths_match_drik():
    plan = P.day_plan(date(2026, 10, 18), *DELHI, "Vulture")
    assert plan["paksha"] == "Shukla"
    mins = [round((s["end"] - s["start"]).total_seconds() / 60) for s in plan["yamas"][0]["subs"]]
    assert all(abs(a - b) <= 1 for a, b in zip(mins, [29, 34, 46, 17, 11]))


def test_best_windows_and_lookup():
    plan = P.day_plan(date(2026, 11, 1), *DELHI, "Vulture")
    best = P.best_windows(plan)
    assert best and all(b["main"] in ("Ruling", "Eating") and b["activity"] in ("Ruling", "Eating") for b in best)
    assert best == sorted(best, key=lambda s: s["start"])
    chosen = {b["start"] for b in best}
    left = [s["score"] for y in plan["yamas"] for s in y["subs"] if s["rating"] == "best" and s["start"] not in chosen]
    assert not left or min(b["score"] for b in best) >= max(left)
    now = P.at(plan, datetime(2026, 11, 1, 7, 0, tzinfo=IST))
    assert now["yama"]["activity"] == "Walking" and now["sub"]["activity"] == "Walking"
    assert P.at(plan, datetime(2026, 11, 1, 5, 0, tzinfo=IST)) is None  # before sunrise: the previous day's night
