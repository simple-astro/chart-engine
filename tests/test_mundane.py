"""Mundane year charts (core/mundane.py): king and minister of the year against published panchangs."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core import mundane as M

DELHI = (28.6139, 77.2090)


@pytest.mark.parametrize("year,samvatsara,raja,mantri", [
    (2023, "Shobhakrit", "Mercury", "Venus"),   # Gudi Padwa Wed 22 Mar 2023; Samvat 2080
    (2024, "Krodhi", "Mars", "Saturn"),         # Tue 9 Apr 2024; Samvat 2081
    (2025, "Vishvavasu", "Sun", "Sun"),         # Sun 30 Mar 2025; Samvat 2082
    (2026, "Parabhava", "Jupiter", "Mars"),     # Thu 19 Mar 2026 (a kshaya Pratipada); Samvat 2083
])
def test_king_and_minister_of_the_year(year, samvatsara, raja, mantri):
    r = M.year_charts(year, *DELHI)
    assert (r["samvatsara"], r["raja"], r["mantri"]) == (samvatsara, raja, mantri)
    assert r["vikram_samvat"] == year + 57


def test_mesha_sankranti_is_the_sun_entering_aries():
    from core.ephemeris import julian_day
    from core.grahas import compute_grahas
    ms = M.mesha_sankranti(2026)
    assert ms.isoformat().startswith("2026-04-14")
    assert abs((compute_grahas(julian_day(ms), "lahiri")["Sun"].longitude + 180) % 360 - 180) < 1e-4


def test_endpoint():
    c = TestClient(app)
    assert c.get("/mundane", params={"year": 2026, "lat": DELHI[0], "lon": DELHI[1]}).json()["raja"] == "Jupiter"
    assert c.get("/mundane", params={"year": 3000, "lat": 0, "lon": 0}).status_code == 422
