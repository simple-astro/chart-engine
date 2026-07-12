# Transit Event-Scan (FR-14 / C1) — Design Spec

**Date:** 2026-07-12
**Repo:** chart-engine (AGPL-3.0, separate service) — sub-project **C1** of Phase 5.
**Scope:** Add a forward-window **transit event scanner** to the chart engine: detect rashi ingress,
retrograde/direct stations, nakshatra changes (slow movers), and solar/lunar eclipses over a date window,
each with an exact UTC time, and expose it as `POST /transit-scan`. Pure astronomy — **no per-user
significance** (that is the backend's FR-14.3, sub-project C2). Keeps Swiss Ephemeris inside the AGPL
boundary; the backend consumes this over HTTP behind its `ChartEngine` port.

**Status:** Approved — implementation to follow. Branch `feat/transit-scan` off `main`.

**Out of scope:** per-user relevance/significance rules, prediction generation, delivery (all backend/C2);
eclipse *visibility from a location* (v1 reports global eclipses); Moon ingress events (excluded as
high-frequency noise); resolving retrograde-loop triple boundary crossings within a single day (v1 reports
the net daily transition).

## 1. Purpose

FR-14.1/14.2 require a daily scan detecting upcoming major planetary events. The engine already computes
graha positions at an instant (`transit_positions` / `compute_grahas`), each `Graha` carrying
`longitude`, `speed` (deg/day), `sign_index`, `nakshatra_index`, and `retrograde`. This spec adds the
temporal layer: sampling those positions across a window and detecting discrete change events with exact
times, plus eclipse detection via Swiss Ephemeris' own event finders.

## 2. Detection method

`scan_events(start_utc, days=7, ayanamsha="krishnamurti", node_type="mean")`:

1. Sample each relevant graha at **daily** resolution across `t ∈ {start, start+1d, …, start+days}` using
   `compute_grahas(julian_day(t), ayanamsha, node_type)`.
2. Between consecutive daily samples, detect a discrete change and **bisection-refine** the exact instant
   to ≤ 60 s:
   - **Ingress:** `sign_index` differs → refine to the 30° sidereal boundary crossing.
   - **Station:** `speed` changes sign → refine to `speed == 0`.
   - **Nakshatra change:** `nakshatra_index` differs → refine to the 13°20′ boundary.
3. Eclipses are found separately via Swiss Ephemeris event finders (§4), not by sampling.
4. Return a list of `TransitEvent`, sorted ascending by `exact_at_utc`.

**Bisection** (`_refine_crossing`): given `[t_lo, t_hi]` bracketing a change in a monotone discrete key
(`sign_index`, `nakshatra_index`, or `sign(speed)`), repeatedly evaluate the midpoint and narrow to the
sub-interval still containing the change until `t_hi − t_lo ≤ 60 s`; return `t_hi` (the first instant
after the crossing) as `exact_at_utc`. Refinement recomputes only the one planet's longitude/speed via
`sidereal_longitude` (cheap).

**v1 simplification (documented):** a planet in a retrograde loop can cross the same 30°/13°20′ boundary up
to three times within one day; v1 detects only the net change between daily samples (so a same-day
cross-and-return yields no event, and a net single crossing yields one event). This is rare for the slow
movers that dominate alerts and is acceptable for v1.

## 3. Event types & graha sets (FR-14.2)

| Event | Grahas | `detail` |
|---|---|---|
| `ingress` | Sun, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu (**no Moon**) | `{from_sign, to_sign, from_sign_index, to_sign_index, direction: "direct"\|"retrograde"}` |
| `station` | Mars, Mercury, Jupiter, Venus, Saturn (Sun/Moon never retrograde; mean Rahu/Ketu always retrograde → no station) | `{direction: "retrograde"\|"direct"}` — retrograde = stationing retrograde (speed + → −); direct = stationing direct (− → +) |
| `nakshatra_change` | Jupiter, Saturn, Rahu, Ketu (slow movers) | `{from_nakshatra, to_nakshatra, from_index, to_index}` |
| `eclipse` | `"Sun"` (solar) / `"Moon"` (lunar) | `{kind: "solar"\|"lunar", eclipse_type: "total"\|"annular"\|"partial"\|"penumbral", magnitude: float}` |

`direction` for ingress reflects the planet's motion at the crossing (retrograde planets ingress
backward). Sign/nakshatra detection uses the requested `ayanamsha` (sidereal); station and eclipse times
are ayanamsha-independent.

## 4. Eclipses

Solar: iterate `swe.sol_eclipse_when_glob(jd, flags, ecl_type=0, backward=False)` from `start`, advancing
past each returned maximum until it falls at/after `start+days`; classify from the returned rflags
(total/annular/partial/hybrid). Lunar: same loop with `swe.lun_eclipse_when(jd, flags, ecl_type=0,
backward=False)` (total/partial/penumbral). Each eclipse's `exact_at_utc` is the peak/maximum instant;
`magnitude` from the returned attributes where available. Only eclipses with peak in `[start, start+days]`
are emitted. (The exact pyswisseph function names/return tuples are verified against the installed
`pyswisseph==2.10.3.2` at implementation time; the design fixes the behavior, not the binding details.)

**`magnitude` — v1 is always `0.0`.** The global finders return no magnitude, and a meaningful solar
magnitude is observer-location dependent (per-location eclipse visibility/magnitude is out of scope, §8).
The `magnitude` field is retained for contract stability but C2 must not build significance on it.

## 5. API

- **Core:** `core/transit_scan.py`:
  - `@dataclass(frozen=True) TransitEvent(type: str, planet: str, exact_at_utc: datetime, detail: dict)`.
  - `scan_events(start_utc: datetime, days: int = 7, ayanamsha: str = "krishnamurti",
    node_type: str = "mean") -> list[TransitEvent]`.
- **HTTP** (`app/routes.py`, `app/schemas.py`): `POST /transit-scan` with
  `TransitScanRequest{start: datetime (tz-aware), days: int = 7 (1..31), ayanamsha, node_type}` →
  `{"events": [{"type", "planet", "exact_at", "detail"}]}`, `exact_at` ISO-8601 UTC, sorted ascending.
  This response is the exact contract the backend's `ChartEngine.scan_events` port and `FakeChartEngine`
  will mirror in C2.

## 6. Testing (reference-based)

The repo tests against trusted published values; the transit-scan tests do the same, using concrete
astronomical events selected at implementation time from published ephemeris data, with a few-minutes
timing tolerance:

- **Ingress:** a window bracketing a documented slow-mover sign change (e.g. a known Jupiter or Saturn
  rashi ingress) → one `ingress` event with correct `from_sign`/`to_sign` and `exact_at_utc` within
  tolerance of the published date/time; the Moon is never emitted as an ingress.
- **Station:** a window bracketing a documented Mercury (or Mars) retrograde and a direct station → the
  right `station` events with correct `direction` on the right dates.
- **Nakshatra change:** a window bracketing a documented slow-mover nakshatra crossing → detected with
  correct `from_nakshatra`/`to_nakshatra`.
- **Eclipse:** a window bracketing a documented solar eclipse and one bracketing a documented lunar
  eclipse → each detected with correct `kind`/`eclipse_type` and peak within minutes.
- **Quiet window:** a window with no slow-mover events yields no spurious ingress/station/nakshatra events.
- **Determinism:** identical inputs → identical event list (order and values), matching the engine's
  existing determinism guarantees.
- **API:** `POST /transit-scan` returns the serialized events sorted by `exact_at`, days-range validated
  (422 outside 1..31).

## 7. Decisions made (stated)

- Daily sampling + bisection refinement to ≤ 60 s; eclipses via Swiss Ephemeris event finders.
- Ingress excludes the Moon; stations only for retrograding planets; nakshatra-change only for slow
  movers; eclipses global (no per-location visibility).
- Sign/nakshatra events honor the requested ayanamsha; stations/eclipses ayanamsha-independent.
- Event contract (`type`, `planet`, `exact_at`, `detail`) fixed here as the C2 consumption contract.
- Retrograde-loop same-day triple crossings reduced to the net daily transition (v1).

## 8. Out of scope / seams for later

- Per-user significance (backend C2), prediction generation, delivery.
- Per-location eclipse visibility; sub-day multi-crossing resolution; ingress for the Moon; finer than
  60 s refinement; additional event types (e.g., planetary war, specific yogas).
