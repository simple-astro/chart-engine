# Chart Engine — Design Spec

**Date:** 2026-07-05
**Scope:** FR-3 (and the compute parts of FR-3.8) of the Jyotish Advisor Platform PRD.
**Status:** Approved — implementation in progress.

## 1. Purpose & boundary

A standalone FastAPI service (its own repo, licensed **AGPL-3.0**) that owns all
astronomy for the platform. Given birth data (or a datetime + location) it returns
deterministic structured chart JSON. The main backend calls it over an internal HTTP
API; **only this service links Swiss Ephemeris** (AGPL isolation, FR-3.9). No database,
no AWS, no auth — pure compute. Runs locally with `uvicorn`.

Built fresh on `pyswisseph` (decided). The `panchang` module is isolated behind a clean
interface so the owner's existing Panchang logic can be folded in later (FR-3.10).

## 2. Repository layout

```
chart-engine/
  LICENSE                 # AGPL-3.0
  README.md               # source-offer notice (AGPL §13)
  pyproject.toml          # pinned deps
  app/
    main.py               # FastAPI app + startup (ayanamsha default, version)
    routes.py             # endpoints
    schemas.py            # pydantic request/response models
  core/
    constants.py          # nakshatra lords, dasha years, sign lords, varga defs
    ephemeris.py          # julian day, sidereal positions, ayanamsha, config
    grahas.py             # 9 grahas: lon, retro, combust, rashi/nakshatra/pada
    houses.py             # lagna + cusps (Placidus KP / whole-sign classical)
    kp.py                 # sub-lord chains (graha + cusp) + significator tables
    vargas.py             # 16 divisional charts from D1
    dasha.py              # Vimshottari 3-level tree with dates
    panchang.py           # tithi/nakshatra/yoga/karana/sunrise-set/rahu kalam
    transits.py           # positions at arbitrary datetime; event helpers
    chart.py              # orchestrates a full natal chart from birth data
  tests/
    golden/*.json         # regression snapshots
    test_anchors.py       # independently-verifiable astronomical values
    test_reference_charts.py
```

## 3. HTTP API (FR-3.2 / FR-3.8)

- `POST /chart` — full natal chart from birth data (the FR-3.3 depth set).
- `POST /transits` — graha positions at an arbitrary datetime + location.
- `POST /panchang` — panchang for a date + location.
- `GET /health`, `GET /version` — engine version, swe version, active ayanamsha.

## 4. Astronomy decisions (verified against pyswisseph 2.10.03)

- **Ephemeris source:** `FLG_MOSEPH | FLG_SIDEREAL | FLG_SPEED`. The Moshier model is
  built into pyswisseph and needs no data files while staying accurate to well under an
  arc-minute for the modern era. `version` exposes the active mode; swapping in the full
  `sepl/semo/seas` `.se1` files later is a drop-in (set ephe path + `FLG_SWIEPH`).
- **Ayanamsha:** KP/Krishnamurti default (`SIDM_KRISHNAMURTI`), Lahiri selectable
  (`SIDM_LAHIRI`); per-request with a server default. Verified KP ayanamsha @J2000 =
  23.760240°.
- **House system bound to mode (FR-3.3a):** Placidus in KP mode (`swe.houses_ex(..., b'P',
  FLG_SIDEREAL)`), whole-sign in classical/Lahiri mode (computed manually: house 1 = the
  sign of the ascendant, subsequent houses follow whole signs).
- **Nodes:** mean node default (`MEAN_NODE`), true node configurable (`TRUE_NODE`);
  Ketu = (Rahu + 180) mod 360.
- **Retrograde:** ecliptic speed < 0. **Combustion:** within per-planet orb of the Sun.
- **Nakshatra:** 27 × 13°20′; pada = quarter of a nakshatra.
- **KP sub-lords:** Vimshottari proportional division within each nakshatra →
  sign-lord → star (nakshatra) lord → sub-lord → sub-sub-lord, computed for all 9 grahas
  and all 12 cusps. Significator tables (4-level house significators per planet and planet
  significators per house) derived from that.
- **Vargas:** all 16 (D1,D2,D3,D4,D7,D9,D10,D12,D16,D20,D24,D27,D30,D40,D45,D60) from D1.
- **Dasha:** Vimshottari from Moon's nakshatra, balance-at-birth, full MD→AD→PD tree with
  exact dates.
- **Determinism (FR-3.4):** key-sorted JSON, degrees to ≥4 decimals, output carries
  `julian_day`, `ayanamsha` value, node type, and engine/swe versions. Identical inputs +
  version ⇒ byte-identical output.

## 5. Testing strategy (golden-master + anchors)

- **Anchors** (`test_anchors.py`) — verifiable by reasoning, catch real logic bugs:
  KP ayanamsha @J2000 ≈ 23.7602°; Ketu exactly opposite Rahu; dasha years sum to 120;
  nakshatra span = 13°20′ and sub-lord spans sum to it; a whole nakshatra's sub-lord chain
  starts with its own lord; pada in 1..4.
- **Golden master** (`test_reference_charts.py`) — 2–3 fixed birth charts snapshotted to
  `tests/golden/*.json`; any drift fails. The owner later diffs one chart against Horosoft/KP
  software and we promote those exact numbers to hard assertions.

## 6. Build milestones (TDD, each green before next)

a. ephemeris + grahas + lagna/houses + anchors
b. KP sub-lord chains + significators
c. 16 vargas
d. 3-level Vimshottari dasha
e. panchang + transits
f. FastAPI wiring + golden snapshots

## 7. Out of scope (this sub-project)

Everything not FR-3: auth, DB persistence, LLM, RAG, Telegram, AWS/CI-CD. The main backend
stores the returned JSON (FR-3.4) — this service does not persist.
