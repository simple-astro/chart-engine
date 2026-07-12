# Transit Event-Scan (FR-14 / C1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a forward-window transit event scanner to the chart engine that detects rashi ingress, retrograde/direct stations, nakshatra changes (slow movers), and solar/lunar eclipses with exact UTC times, exposed as `POST /transit-scan`.

**Architecture:** `scan_events(start, days, …)` samples graha positions daily via the existing `compute_grahas`, detects discrete `sign_index`/`retrograde`/`nakshatra_index` changes between samples, and bisection-refines each to ≤60 s; eclipses come from Swiss Ephemeris' own event finders. A thin FastAPI route serializes the events.

**Tech Stack:** Python, pyswisseph (`swisseph`), FastAPI, pytest. Repo: chart-engine (AGPL). No new dependency.

## Global Constraints

- Ingress grahas: Sun, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu — **NOT the Moon**.
- Station grahas: Mars, Mercury, Jupiter, Venus, Saturn (Sun/Moon never retrograde; mean Rahu/Ketu always retrograde → no station).
- Nakshatra-change grahas: Jupiter, Saturn, Rahu, Ketu (slow movers only).
- Refinement: bisection to ≤ 60 s; `exact_at_utc` is the first instant after the crossing.
- Sign/nakshatra detection honors the requested `ayanamsha`; station and eclipse times are ayanamsha-independent.
- Event contract (the shape the backend C2 consumes): `TransitEvent(type, planet, exact_at_utc, detail)`; over HTTP `{type, planet, exact_at (ISO UTC), detail}`, events sorted ascending by time.
- v1 simplification: a retrograde-loop same-day triple crossing is reduced to the net daily transition.
- Tests are **self-consistency + astronomical-invariant** (no hardcoded external ephemeris minutes): verify each event's `exact_at` is the real boundary by recomputing positions ±2 min around it, and assert counts/invariants over long windows. Deterministic.
- Run tests from `chart-engine/`: `.venv/bin/python -m pytest`. Commit at the end of each task with the given message.

---

### Task 1: Core scanner — ingress, station, nakshatra + refinement

**Files:**
- Create: `core/transit_scan.py`
- Test: `tests/test_transit_scan.py`

**Interfaces:**
- Consumes: `compute_grahas(jd, ayanamsha, node_type) -> dict[str, Graha]` (Graha has `longitude, speed, sign_index, sign, nakshatra_index, nakshatra, retrograde`); `julian_day(dt_utc)`.
- Produces: `TransitEvent(type: str, planet: str, exact_at_utc: datetime, detail: dict)`; `scan_events(start_utc, days=7, ayanamsha="krishnamurti", node_type="mean") -> list[TransitEvent]` (ingress/station/nakshatra only; eclipses added in Task 2); module tuples `INGRESS_GRAHAS`, `STATION_GRAHAS`, `NAKSHATRA_GRAHAS`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transit_scan.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_transit_scan.py -q`
Expected: FAIL — `ModuleNotFoundError: core.transit_scan`.

- [ ] **Step 3: Implement the scanner**

Create `core/transit_scan.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.ephemeris import julian_day
from core.grahas import compute_grahas

INGRESS_GRAHAS = ("Sun", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")  # no Moon
STATION_GRAHAS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NAKSHATRA_GRAHAS = ("Jupiter", "Saturn", "Rahu", "Ketu")

_REFINE_SECONDS = 60


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

    events.sort(key=lambda e: e.exact_at_utc)
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_transit_scan.py -q`
Expected: PASS. (If `test_station_events_only_for_retrograding_planets` finds zero stations in 400 days — unlikely — widen the window; Mercury alone retrogrades ~3×/yr.)

- [ ] **Step 5: Commit**

```bash
git add core/transit_scan.py tests/test_transit_scan.py
git commit -m "feat(transit): scan_events ingress/station/nakshatra detection with bisection refinement"
```

---

### Task 2: Eclipse detection

**Files:**
- Modify: `core/transit_scan.py` (add `_scan_eclipses`, call it in `scan_events`)
- Test: `tests/test_transit_scan.py` (extend)

**Interfaces:**
- Consumes: Swiss Ephemeris eclipse finders `swe.sol_eclipse_when_glob`, `swe.lun_eclipse_when`, `swe.revjul`.
- Produces: `eclipse` events in `scan_events` output: `TransitEvent("eclipse", "Sun"|"Moon", peak_utc, {kind, eclipse_type, magnitude})`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_transit_scan.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_transit_scan.py::test_eclipses_detected_over_a_year -q`
Expected: FAIL — no eclipse events yet.

- [ ] **Step 3: Implement eclipse detection**

First VERIFY the installed pyswisseph API in a REPL and adapt the code below to the real signatures/constants:

```bash
.venv/bin/python -c "import swisseph as swe; help(swe.sol_eclipse_when_glob); print([n for n in dir(swe) if 'ECL' in n])"
```

Then add to `core/transit_scan.py` (import `swisseph as swe` at the top):

```python
_ECL_FLAG = swe.FLG_SWIEPH   # matches the engine's default ephemeris; adjust to swe.FLG_MOSEPH if
                             # eclipse funcs require it in this environment (verify in Step 3 REPL).


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
    for _ in range(60):                              # safety bound (>>eclipses per window)
        rflags, tret = swe.sol_eclipse_when_glob(jd, _ECL_FLAG, 0, False)
        peak = tret[0]
        if peak > jd_end:
            break
        events.append(TransitEvent("eclipse", "Sun", _jd_to_utc(peak),
                                   {"kind": "solar", "eclipse_type": _solar_type(rflags), "magnitude": 0.0}))
        jd = peak + 1.0

    jd = julian_day(start)
    for _ in range(60):
        rflags, tret = swe.lun_eclipse_when(jd, _ECL_FLAG, 0, False)
        peak = tret[0]
        if peak > jd_end:
            break
        events.append(TransitEvent("eclipse", "Moon", _jd_to_utc(peak),
                                   {"kind": "lunar", "eclipse_type": _lunar_type(rflags), "magnitude": 0.0}))
        jd = peak + 1.0

    return [e for e in events if start <= e.exact_at_utc <= end]
```

In `scan_events`, before the final `events.sort(...)`, add:

```python
    events.extend(_scan_eclipses(start, end))
```

(`magnitude` is best-effort `0.0` in v1; if `swe.sol_eclipse_how`/`lun_eclipse_how` is trivially available in Step 3's REPL check, populate it, otherwise leave `0.0` — the contract keeps the field.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_transit_scan.py -q`
Expected: PASS (all Task 1 tests + the two eclipse tests).

- [ ] **Step 5: Commit**

```bash
git add core/transit_scan.py tests/test_transit_scan.py
git commit -m "feat(transit): solar/lunar eclipse detection via Swiss Ephemeris finders"
```

---

### Task 3: `POST /transit-scan` endpoint

**Files:**
- Modify: `app/schemas.py` (`TransitScanRequest`)
- Modify: `app/routes.py` (`POST /transit-scan`)
- Test: `tests/test_api.py` (extend)

**Interfaces:**
- Consumes: `scan_events` (Tasks 1–2).
- Produces: `POST /transit-scan` → `{start, days, events: [{type, planet, exact_at, detail}]}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py` (match the file's existing TestClient usage — read it first):

```python
def test_transit_scan_endpoint_returns_sorted_events(client):
    r = client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 45})
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 45 and isinstance(body["events"], list)
    times = [e["exact_at"] for e in body["events"]]
    assert times == sorted(times)
    for e in body["events"]:
        assert set(e.keys()) == {"type", "planet", "exact_at", "detail"}
        assert e["type"] in ("ingress", "station", "nakshatra_change", "eclipse")

def test_transit_scan_days_out_of_range_422(client):
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 0}).status_code == 422
    assert client.post("/transit-scan", json={"start": "2026-01-01T00:00:00Z", "days": 99}).status_code == 422
```

(If `tests/test_api.py` builds its `client` differently — e.g. a module-level `TestClient(app)` rather than a fixture — match that exact pattern.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -q -k transit_scan`
Expected: FAIL — route 404.

- [ ] **Step 3: Add the schema**

In `app/schemas.py`, add (reusing the existing `Ayanamsha`/`NodeType` `Literal`s and `Field`):

```python
class TransitScanRequest(BaseModel):
    start: datetime = Field(description="Timezone-aware UTC datetime; naive is treated as UTC")
    days: int = Field(default=7, ge=1, le=31)
    ayanamsha: Ayanamsha = "krishnamurti"
    node_type: NodeType = "mean"
```

- [ ] **Step 4: Add the route**

In `app/routes.py`, add `from core.transit_scan import scan_events` and `from app.schemas import TransitScanRequest` (match the file's import style), then:

```python
@router.post("/transit-scan")
def transit_scan(req: TransitScanRequest) -> dict:
    start = req.start if req.start.tzinfo else req.start.replace(tzinfo=timezone.utc)
    events = scan_events(start, req.days, req.ayanamsha, req.node_type)
    return {
        "start": start.astimezone(timezone.utc).isoformat(),
        "days": req.days,
        "events": [{"type": e.type, "planet": e.planet,
                    "exact_at": e.exact_at_utc.isoformat(), "detail": e.detail} for e in events],
    }
```

(`timezone` is already imported in `routes.py`; if not, add `from datetime import timezone`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (existing 61 + the new transit-scan + API tests).

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routes.py tests/test_api.py
git commit -m "feat(transit): POST /transit-scan endpoint"
```

---

## Self-Review

**Spec coverage:**
- FR-14.2 ingress (all except Moon), stations (retrograding planets), nakshatra change (slow movers), eclipses (solar+lunar) → Task 1 (first three) + Task 2 (eclipses). ✓
- Forward window, daily scan + refinement → Task 1 sampling + `_refine`. ✓
- Exact UTC times → `_refine` to ≤60 s; eclipse peak. ✓
- Event contract (type/planet/exact_at/detail) → Task 1 dataclass, Task 3 serialization. ✓
- `POST /transit-scan` → Task 3. ✓
- Determinism + reference/invariant testing → Task 1/2 tests (self-consistency + astronomical invariants). ✓

**Placeholder scan:** No TBD/TODO. Task 2 Step 3 instructs a REPL verification of the pyswisseph eclipse API before finalizing — this is a deliberate, concrete verification step (the design fixes behavior; the exact binding names are environment-verified), with adaptable code shown, not a placeholder. `magnitude` is explicitly a best-effort `0.0` with the field kept for contract stability.

**Type consistency:** `TransitEvent(type, planet, exact_at_utc, detail)` and `scan_events(start_utc, days, ayanamsha, node_type)` are used identically across Tasks 1→3. `INGRESS_GRAHAS`/`STATION_GRAHAS`/`NAKSHATRA_GRAHAS` referenced by tests match the module. The HTTP field is `exact_at` (serialized) mapping from `exact_at_utc` (dataclass) — consistent in Task 3 serialization and the API test.
