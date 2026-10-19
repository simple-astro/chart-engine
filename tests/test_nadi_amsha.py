"""D150, the Nadi amsha, numbered the Chandra Kala Nadi way."""
from datetime import date, time

from core import nadi_amsha as na
from core.chart import BirthData, compute_natal_chart
from core.vargas import varga_sign


def test_movable_signs_count_forward():
    assert na.number(0.0) == 1 and na.number(0.21) == 2 and na.number(29.99) == 150   # Aries
    assert na.number(90.1) == 1                                                        # Cancer


def test_fixed_signs_count_back_from_the_end():
    assert na.number(30.0) == 150 and na.number(59.99) == 1                            # Taurus
    assert na.number(120 + 14.8) == 150 - 74                                           # Leo 14°48′ is part 76


def test_dual_signs_count_from_the_middle():
    assert na.number(60 + 15.0) == 1 and na.number(60 + 29.99) == 75                   # Gemini
    assert na.number(240.0) == 76 and na.number(240 + 14.99) == 150                    # Sagittarius


def test_d150_sign_counts_on_from_the_sign_itself():
    assert na.d150_sign(0.0) == 0                     # Aries part 1: Aries
    assert na.d150_sign(30.0) == (1 + 149) % 12       # Taurus part 150
    assert varga_sign(120 + 14.8, 150) == na.d150_sign(120 + 14.8) == (4 + 75) % 12   # Leo part 76: Scorpio


def test_point_reports_the_part_range():
    p = na.point(240 + 1.27)
    assert p["sign"] == "Sagittarius" and p["number"] == 82
    assert abs(p["from"] - 1.2) < 1e-6 and abs(p["to"] - 1.4) < 1e-6


def test_lagna_window_brackets_one_part():
    b = BirthData(name="T", dob=date(1990, 5, 15), tob=time(14, 30), lat=28.6139, lon=77.209, tz_name="Asia/Kolkata")
    c = compute_natal_chart(b)
    a = na.analyse(c, b.lat, b.lon)
    w = a["lagna_window"]
    assert a["counting"] == "Chandra Kala Nadi" and set(a["points"]) >= {"Lagna", "Sun", "Ketu"}
    assert 1 <= w["earlier"] and 1 <= w["later"] and 20 <= w["earlier"] + w["later"] <= 200   # one part ≈ 48 s
