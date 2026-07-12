from datetime import datetime, timedelta, timezone

from core.transit_scan import scan_events, TransitEvent, INGRESS_GRAHAS

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)

def _events(days, kinds=None, ayanamsha="krishnamurti"):
    evs = scan_events(START, days=days, ayanamsha=ayanamsha)
    return [e for e in evs if kinds is None or e.type in kinds]

def _sign_index_at(t, name):
    from core.grahas import compute_grahas
    from core.ephemeris import julian_day
    return compute_grahas(julian_day(t), "krishnamurti", "mean")[name].sign_index

def _retro_at(t, name):
    from core.grahas import compute_grahas
    from core.ephemeris import julian_day
    return compute_grahas(julian_day(t), "krishnamurti", "mean")[name].retrograde

def test_returns_sorted_events():
    evs = scan_events(START, days=45)
    assert all(isinstance(e, TransitEvent) for e in evs)
    assert evs == sorted(evs, key=lambda e: e.exact_at_utc)

def test_moon_never_emitted_as_ingress():
    evs = scan_events(START, days=200)
    assert all(e.planet != "Moon" for e in evs if e.type == "ingress")

def test_ingress_exact_time_is_the_real_boundary():
    # every ingress event's exact_at must sit on the sign boundary: the planet is
    # in from_sign just before and to_sign just after (proves refinement exactness).
    for e in _events(120, {"ingress"}):
        before = _sign_index_at(e.exact_at_utc - timedelta(minutes=2), e.planet)
        after = _sign_index_at(e.exact_at_utc + timedelta(minutes=2), e.planet)
        assert before == e.detail["from_sign_index"]
        assert after == e.detail["to_sign_index"]
        assert before != after

def test_sun_ingress_is_roughly_monthly():
    sun = [e for e in _events(400, {"ingress"}) if e.planet == "Sun"]
    assert len(sun) >= 12   # Sun changes sign ~once a month

def test_station_events_only_for_retrograding_planets():
    from core.transit_scan import STATION_GRAHAS
    stations = _events(400, {"station"})
    assert stations, "expected at least one station over 400 days"
    assert all(e.planet in STATION_GRAHAS for e in stations)
    for e in stations:
        assert e.detail["direction"] in ("retrograde", "direct")

def test_station_exact_time_flips_retrograde():
    for e in _events(200, {"station"}):
        before = _retro_at(e.exact_at_utc - timedelta(minutes=2), e.planet)
        after = _retro_at(e.exact_at_utc + timedelta(minutes=2), e.planet)
        assert before != after
        assert after == (e.detail["direction"] == "retrograde")

def test_mercury_retrogrades_a_few_times_a_year():
    merc = [e for e in _events(400, {"station"}) if e.planet == "Mercury"]
    assert len(merc) >= 3   # ~3 retrograde + ~3 direct stations per year

def test_nakshatra_change_only_slow_movers():
    from core.transit_scan import NAKSHATRA_GRAHAS
    for e in _events(400, {"nakshatra_change"}):
        assert e.planet in NAKSHATRA_GRAHAS
        assert e.detail["from_index"] != e.detail["to_index"]

def test_determinism():
    a = scan_events(START, days=120)
    b = scan_events(START, days=120)
    assert [(e.type, e.planet, e.exact_at_utc, e.detail) for e in a] == \
           [(e.type, e.planet, e.exact_at_utc, e.detail) for e in b]

def test_eclipses_detected_over_a_year():
    evs = scan_events(START, days=365)
    ecl = [e for e in evs if e.type == "eclipse"]
    solar = [e for e in ecl if e.planet == "Sun"]
    lunar = [e for e in ecl if e.planet == "Moon"]
    assert len(solar) >= 1 and len(lunar) >= 1     # every year has >=2 solar and >=2 lunar
    for e in ecl:
        assert e.detail["kind"] in ("solar", "lunar")
        assert e.detail["eclipse_type"] in ("total", "annular", "partial", "penumbral", "hybrid")
        assert START <= e.exact_at_utc <= START + timedelta(days=365)

def test_no_eclipses_when_none_in_short_window_does_not_crash():
    # a short window may legitimately contain no eclipse; must return [] for that type, not error
    evs = scan_events(START, days=3)
    assert isinstance(evs, list)
