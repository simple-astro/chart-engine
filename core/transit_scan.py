from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import swisseph as swe

from core.ephemeris import julian_day
from core.grahas import compute_grahas

INGRESS_GRAHAS = ("Sun", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")  # no Moon
STATION_GRAHAS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NAKSHATRA_GRAHAS = ("Jupiter", "Saturn", "Rahu", "Ketu")

_REFINE_SECONDS = 60

# The engine's default calculation flag is FLG_MOSEPH (see core/ephemeris.py: no
# ephe path configured by default). Eclipse finders return identical results under
# FLG_SWIEPH and FLG_MOSEPH in this environment (no Swiss Ephemeris data files are
# loaded either way), so FLG_MOSEPH is used here to stay consistent with the rest
# of the engine's default behavior.
_ECL_FLAG = swe.FLG_MOSEPH
_ECL_MAX_ITERATIONS = 60  # safety bound (>>eclipses per window)


@dataclass(frozen=True)
class TransitEvent:
    type: str
    planet: str
    exact_at_utc: datetime
    detail: dict


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _grahas_at(t: datetime, ayanamsha: str, node_type: str):
    return compute_grahas(julian_day(t), ayanamsha, node_type)


def _refine(t_lo: datetime, t_hi: datetime, name: str, keyfn, ayanamsha: str, node_type: str) -> datetime:
    """Bisect [t_lo, t_hi] (which bracket a change in the discrete keyfn) until the
    interval is <= 60 s; return t_hi, the first instant after the crossing."""
    k_lo = keyfn(_grahas_at(t_lo, ayanamsha, node_type)[name])
    while (t_hi - t_lo).total_seconds() > _REFINE_SECONDS:
        mid = t_lo + (t_hi - t_lo) / 2
        if keyfn(_grahas_at(mid, ayanamsha, node_type)[name]) == k_lo:
            t_lo = mid
        else:
            t_hi = mid
    return t_hi


def _jd_to_utc(jd_ut: float) -> datetime:
    y, m, d, h = swe.revjul(jd_ut)
    return datetime(int(y), int(m), int(d), tzinfo=timezone.utc) + timedelta(hours=h)


def _solar_type(rflags: int) -> str:
    if rflags & swe.ECL_TOTAL:
        return "total"
    if rflags & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if rflags & swe.ECL_ANNULAR:
        return "annular"
    return "partial"


def _lunar_type(rflags: int) -> str:
    if rflags & swe.ECL_TOTAL:
        return "total"
    if rflags & swe.ECL_PARTIAL:
        return "partial"
    return "penumbral"


def _scan_eclipses(start: datetime, end: datetime) -> list[TransitEvent]:
    jd_end = julian_day(end)
    events: list[TransitEvent] = []

    jd = julian_day(start)
    for _ in range(_ECL_MAX_ITERATIONS):
        rflags, tret = swe.sol_eclipse_when_glob(jd, _ECL_FLAG, 0, False)
        peak = tret[0]
        if peak > jd_end:
            break
        events.append(TransitEvent("eclipse", "Sun", _jd_to_utc(peak),
                                   {"kind": "solar", "eclipse_type": _solar_type(rflags), "magnitude": 0.0}))
        jd = peak + 1.0

    jd = julian_day(start)
    for _ in range(_ECL_MAX_ITERATIONS):
        rflags, tret = swe.lun_eclipse_when(jd, _ECL_FLAG, 0, False)
        peak = tret[0]
        if peak > jd_end:
            break
        events.append(TransitEvent("eclipse", "Moon", _jd_to_utc(peak),
                                   {"kind": "lunar", "eclipse_type": _lunar_type(rflags), "magnitude": 0.0}))
        jd = peak + 1.0

    return [e for e in events if start <= e.exact_at_utc <= end]


def scan_events(start_utc: datetime, days: int = 7, ayanamsha: str = "krishnamurti",
                node_type: str = "mean") -> list[TransitEvent]:
    start = _ensure_utc(start_utc)
    end = start + timedelta(days=days)

    samples = []
    t = start
    while t <= end:
        samples.append((t, _grahas_at(t, ayanamsha, node_type)))
        t += timedelta(days=1)

    events: list[TransitEvent] = []
    for (t0, g0), (t1, g1) in zip(samples, samples[1:]):
        for name in INGRESS_GRAHAS:
            if g0[name].sign_index != g1[name].sign_index:
                exact = _refine(t0, t1, name, lambda g: g.sign_index, ayanamsha, node_type)
                after = _grahas_at(exact, ayanamsha, node_type)[name]
                events.append(TransitEvent("ingress", name, exact, {
                    "from_sign": g0[name].sign, "to_sign": g1[name].sign,
                    "from_sign_index": g0[name].sign_index, "to_sign_index": g1[name].sign_index,
                    "direction": "retrograde" if after.retrograde else "direct"}))
        for name in STATION_GRAHAS:
            if g0[name].retrograde != g1[name].retrograde:
                exact = _refine(t0, t1, name, lambda g: g.retrograde, ayanamsha, node_type)
                events.append(TransitEvent("station", name, exact, {
                    "direction": "retrograde" if g1[name].retrograde else "direct"}))
        for name in NAKSHATRA_GRAHAS:
            if g0[name].nakshatra_index != g1[name].nakshatra_index:
                exact = _refine(t0, t1, name, lambda g: g.nakshatra_index, ayanamsha, node_type)
                events.append(TransitEvent("nakshatra_change", name, exact, {
                    "from_nakshatra": g0[name].nakshatra, "to_nakshatra": g1[name].nakshatra,
                    "from_index": g0[name].nakshatra_index, "to_index": g1[name].nakshatra_index}))

    events.extend(_scan_eclipses(start, end))

    events.sort(key=lambda e: e.exact_at_utc)
    return events
