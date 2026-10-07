"""HTTP routes for the Chart Engine."""
from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, HTTPException

from app.schemas import ChartRequest, PanchangRequest, TransitRequest, TransitScanRequest
from core import ephemeris
from core.ashtakavarga import ashtakavarga
from core.chart import ENGINE_VERSION, BirthData, compute_natal_chart
from core.grahas import Graha
from core.parivartana import exchanges, lord_placements
from core.panchang import compute_panchang
from core.transit_scan import scan_events
from core.transits import transit_positions
from core.vargas import varga_sign

router = APIRouter()


def _graha_to_dict(g: Graha) -> dict:
    return {
        "longitude": round(g.longitude, 6),
        "speed": round(g.speed, 6),
        "sign": g.sign,
        "sign_index": g.sign_index,
        "sign_lord": g.sign_lord,
        "degrees_in_sign": round(g.degrees_in_sign, 6),
        "nakshatra": g.nakshatra,
        "nakshatra_index": g.nakshatra_index,
        "nakshatra_lord": g.nakshatra_lord,
        "pada": g.pada,
        "retrograde": g.retrograde,
        "combust": g.combust,
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/version")
def version() -> dict:
    return {
        "engine_version": ENGINE_VERSION,
        "swe_version": ephemeris.swe_version(),
        "ephemeris_mode": ephemeris.ephe_mode(),
        "default_ayanamsha": "krishnamurti",
    }


@router.post("/chart")
def chart(req: ChartRequest) -> dict:
    birth = BirthData(
        name=req.name,
        dob=req.dob,
        tob=req.tob,
        lat=req.lat,
        lon=req.lon,
        tz_name=req.tz_name,
        tob_unknown=req.tob_unknown,
        ayanamsha=req.ayanamsha,
        node_type=req.node_type,
    )
    try:
        return with_extras(compute_natal_chart(birth))
    except Exception as exc:  # invalid tz, bad inputs -> 422
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def with_extras(c: dict) -> dict:
    """Derived data kept out of the engine's golden output: divisional ascendants,
    Ashtakavarga, and lord exchanges (Rasi and Navamsa)."""
    if "varga_lagna" not in c:
        asc = c["lagna"]["ascendant"]
        c["varga_lagna"] = {k: varga_sign(asc, int(k[1:])) for k in c["vargas"]}
    signs = {p: g["sign_index"] for p, g in c["grahas"].items()}
    lagna = c["lagna"]["sign_index"]
    c["ashtakavarga"] = ashtakavarga(signs, lagna)
    c["lords"] = lord_placements(signs, lagna)
    c["exchanges"] = {"D1": exchanges(signs, lagna)}
    if "D9" in c["vargas"]:
        d9 = {p: v["sign_index"] for p, v in c["vargas"]["D9"].items()}
        c["exchanges"]["D9"] = exchanges(d9, c["varga_lagna"]["D9"])
    return c


@router.post("/transits")
def transits(req: TransitRequest) -> dict:
    when = req.when
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    positions = transit_positions(when, req.ayanamsha, node_type=req.node_type)
    return {
        "when": when.astimezone(timezone.utc).isoformat(),
        "ayanamsha": req.ayanamsha,
        "grahas": {name: _graha_to_dict(g) for name, g in positions.items()},
    }


@router.post("/panchang")
def panchang(req: PanchangRequest) -> dict:
    try:
        p = compute_panchang(req.on, req.lat, req.lon, req.tz_name)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "date": p.date.isoformat(),
        "weekday": p.weekday,
        "sunrise": p.sunrise.isoformat(),
        "sunset": p.sunset.isoformat(),
        "tithi": {"number": p.tithi_number, "paksha": p.paksha,
                  "paksha_index": p.tithi_paksha_index},
        "nakshatra": {"index": p.nakshatra_index, "name": p.nakshatra,
                      "lord": p.nakshatra_lord},
        "yoga": {"number": p.yoga_number, "name": p.yoga},
        "karana": {"number": p.karana_number, "name": p.karana},
        "windows": {
            "rahu_kalam": [p.rahu_kalam[0].isoformat(), p.rahu_kalam[1].isoformat()],
            "yamaganda": [p.yamaganda[0].isoformat(), p.yamaganda[1].isoformat()],
            "gulika": [p.gulika[0].isoformat(), p.gulika[1].isoformat()],
        },
    }


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
