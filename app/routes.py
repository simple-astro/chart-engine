"""HTTP routes for the Chart Engine."""
from __future__ import annotations

import logging
from datetime import timezone

from fastapi import APIRouter, HTTPException

from app.schemas import ChartRequest, PanchangRequest, TransitRequest, TransitScanRequest
from core import ephemeris
from core.ashtakavarga import ashtakavarga
from core.chart import ENGINE_VERSION, BirthData, compute_natal_chart
from core.grahas import Graha
from core import bnn, chara, jaimini, yoga_eval, yogas, yogini
from app import dasha_read
from core import kp_predict, nadi_amsha
from core.constants import SIGNS
from core.parivartana import exchanges, lord_placements
from core.panchang import compute_panchang
from core.transit_scan import scan_events
from core.transits import transit_positions
from core.vargas import varga_sign

router = APIRouter()
log = logging.getLogger(__name__)

# User-facing errors. Exception text (e.g. "'No time zone found with key Foo/Bar'") goes to the log, never the client.
TZ_ERROR = {"field": "tz", "message": "We don't recognise that timezone."}
CALC_ERROR = "We couldn't work this out from those details. Please check them and try again."


def require_tz(name: str | None) -> str:
    """The IANA zone name, or a structured 422 the form can show under its timezone field."""
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(name or "")
    except Exception as exc:  # ZoneInfoNotFoundError, ValueError for malformed keys, TypeError
        raise HTTPException(status_code=422, detail=TZ_ERROR) from exc
    return name


def calc_error(exc: Exception) -> HTTPException:
    log.warning("calculation failed: %r", exc)
    return HTTPException(status_code=422, detail=CALC_ERROR)


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
    require_tz(req.tz_name)
    try:
        c = with_extras(compute_natal_chart(birth))
        c["nadi_amsha"] = nadi_amsha.analyse(c, req.lat, req.lon)
        return c
    except Exception as exc:  # bad inputs -> 422 without the exception text
        raise calc_error(exc) from exc


def with_extras(c: dict) -> dict:
    """Derived data kept out of the engine's golden output: divisional ascendants,
    Ashtakavarga, and lord exchanges (Rasi and Navamsa)."""
    if "D150" not in c["vargas"]:  # the Nadi amsha chart, after the 16 classical vargas
        c["vargas"]["D150"] = {n: {"sign_index": varga_sign(g["longitude"], 150),
                                   "sign": SIGNS[varga_sign(g["longitude"], 150)]} for n, g in c["grahas"].items()}
    if "varga_lagna" not in c:
        asc = c["lagna"]["ascendant"]
        c["varga_lagna"] = {k: varga_sign(asc, int(k[1:])) for k in c["vargas"]}
    c["varga_lagna"].setdefault("D150", varga_sign(c["lagna"]["ascendant"], 150))
    signs = {p: g["sign_index"] for p, g in c["grahas"].items()}
    lagna = c["lagna"]["sign_index"]
    c["ashtakavarga"] = ashtakavarga(signs, lagna)
    c["lords"] = lord_placements(signs, lagna)
    c["exchanges"] = {"D1": exchanges(signs, lagna)}
    d9 = {p: v["sign_index"] for p, v in c["vargas"].get("D9", {}).items()} or None
    if d9:
        c["exchanges"]["D9"] = exchanges(d9, c["varga_lagna"]["D9"])
    c["strength"] = yogas.analyse(signs, lagna, d9, {p: g["combust"] for p, g in c["grahas"].items()})
    c["jaimini"] = jaimini.analyse(c)
    c["chara"] = chara.summary(c)
    c["narayana"] = chara.narayana_dasha(c)
    c["yogini"] = yogini.summary(c)
    c["yoga_check"] = yoga_eval.evaluate(c)
    c["dasha_read"] = dasha_read.summary(c)
    c["bnn"] = bnn.analyse(c)
    # KP: the houses each planet signifies by itself (Rahu and Ketu also through the planets they act for)
    c["kp_houses"] = {p: sorted(kp_predict.own_houses(c, p)) for p in c["grahas"]}
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
    require_tz(req.tz_name)
    try:
        p = compute_panchang(req.on, req.lat, req.lon, req.tz_name)
    except Exception as exc:  # polar day without sunrise
        raise calc_error(exc) from exc
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
