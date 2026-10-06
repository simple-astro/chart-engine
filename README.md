# Jyotish Chart Engine

A standalone service that computes Vedic (Jyotiṣa) astrological chart data — grahas,
lagna & houses, KP sub-lord chains and significators, the 16 divisional charts
(shodashavarga), the Vimśottarī daśā tree, panchang, and transits — from birth details or
an arbitrary datetime and location.

Built on the [Swiss Ephemeris](https://www.astro.com/swisseph/) via
[`pyswisseph`](https://github.com/astrorigin/pyswisseph). It is the astronomy engine for
the Jyotish Advisor Platform and is deliberately isolated: **only this service links Swiss
Ephemeris.** The rest of the platform calls it over an internal HTTP API.

## License & source offer (AGPL-3.0)

This program is free software licensed under the **GNU Affero General Public License v3.0**
(see [`LICENSE`](./LICENSE)). Swiss Ephemeris is used under AGPL-3.0. In accordance with
AGPL §13, users interacting with this service over a network are offered the complete
corresponding source code of this service: <https://github.com/OWNER/chart-engine>
(repository URL to be set by the product owner).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs
```

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

## Endpoints

| Method | Path         | Purpose                                            |
|--------|--------------|----------------------------------------------------|
| POST   | `/chart`     | Full natal chart from birth data                   |
| POST   | `/transits`  | Graha positions at an arbitrary datetime+location  |
| POST   | `/panchang`  | Panchang for a date+location                        |
| GET    | `/health`    | Liveness                                            |
| POST   | `/transit-scan` | Ingresses, retrogrades and eclipses in a window  |
| POST   | `/lal-kitab` | Lal Kitab kundli, debts and remedies (always Lahiri) |
| POST   | `/matchmaking` | Ashtakoota guna milan + Manglik, from two birth records |
| GET    | `/version`   | Engine version, swe version, active ayanamsha mode |

Every endpoint is **stateless**: the request carries its own birth data, nothing is stored,
and the service holds no third-party API keys. User data belongs to the calling platform.
Set `ENV=production` to switch off `/docs`, `/redoc` and `/openapi.json`.

## Configuration

- **Ayanamsha:** `krishnamurti` (KP, default) or `lahiri`. House system is bound to the
  mode — Placidus in KP, whole-sign in classical/Lahiri.
- **Node type:** `mean` (default) or `true`.
- **Ephemeris:** uses the built-in Moshier model (no data files needed). To use the full
  Swiss Ephemeris files, drop `sepl*/semo*/seas*.se1` into an `ephe/` directory and set
  `SE_EPHE_PATH`.
