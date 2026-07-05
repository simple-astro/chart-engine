"""Full natal-chart orchestration.

Assembles the complete FR-3.3 depth set (grahas, KP chains, houses+cusp sub-lords,
significators, 16 vargas, 3-level dasha) into a deterministic, key-sorted JSON
structure with reproducibility metadata (FR-3.4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from core import constants as C
from core import ephemeris, vargas as varga_mod
from core.dasha import DashaPeriod, vimshottari_tree
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.kp import kp_lords, planet_house, planet_significators, house_significators

ENGINE_VERSION = "0.1.0"
_ROUND = 6


@dataclass(frozen=True)
class BirthData:
    name: str
    dob: date
    tob: time
    lat: float
    lon: float
    tz_name: str
    tob_unknown: bool = False
    ayanamsha: str = "krishnamurti"
    node_type: str = "mean"


def _r(x: float) -> float:
    return round(x, _ROUND)


def _kp_dict(longitude: float) -> dict:
    k = kp_lords(longitude)
    return {
        "sign_lord": k.sign_lord,
        "star_lord": k.star_lord,
        "sub_lord": k.sub_lord,
        "sub_sub_lord": k.sub_sub_lord,
    }


def _serialize_dasha(node: DashaPeriod) -> dict:
    return {
        "lord": node.lord,
        "level": node.level,
        "start": node.start.isoformat(),
        "end": node.end.isoformat(),
        "children": [_serialize_dasha(c) for c in node.children],
    }


def birth_datetime_utc(birth: BirthData) -> datetime:
    """Convert local birth date+time to a UTC datetime via the IANA timezone."""
    local = datetime.combine(birth.dob, birth.tob, tzinfo=ZoneInfo(birth.tz_name))
    return local


def compute_natal_chart(birth: BirthData) -> dict:
    local_dt = birth_datetime_utc(birth)
    jd = ephemeris.julian_day(local_dt)

    grahas = compute_grahas(jd, birth.ayanamsha, node_type=birth.node_type)
    houses = compute_houses(jd, birth.lat, birth.lon, birth.ayanamsha)

    graha_out: dict[str, dict] = {}
    for name, g in grahas.items():
        graha_out[name] = {
            "longitude": _r(g.longitude),
            "speed": _r(g.speed),
            "sign": g.sign,
            "sign_index": g.sign_index,
            "sign_lord": g.sign_lord,
            "degrees_in_sign": _r(g.degrees_in_sign),
            "nakshatra": g.nakshatra,
            "nakshatra_index": g.nakshatra_index,
            "nakshatra_lord": g.nakshatra_lord,
            "pada": g.pada,
            "retrograde": g.retrograde,
            "combust": g.combust,
            "house": planet_house(g.longitude, houses),
            "kp": _kp_dict(g.longitude),
        }

    houses_out = [
        {
            "house": c.house,
            "longitude": _r(c.longitude),
            "sign": c.sign,
            "sign_index": c.sign_index,
            "sign_lord": c.sign_lord,
            "degrees_in_sign": _r(c.degrees_in_sign),
            "kp": _kp_dict(c.longitude),
        }
        for c in houses.cusps
    ]

    psig = planet_significators(grahas, houses)
    hsig = house_significators(grahas, houses)

    dasha = [_serialize_dasha(md) for md in vimshottari_tree(grahas["Moon"].longitude, local_dt)]

    return {
        "meta": {
            "name": birth.name,
            "julian_day": _r(jd),
            "ayanamsha": birth.ayanamsha,
            "ayanamsha_value": _r(ephemeris.get_ayanamsha(jd, birth.ayanamsha)),
            "node_type": birth.node_type,
            "house_system": houses.house_system,
            "tob_unknown": birth.tob_unknown,
            "engine_version": ENGINE_VERSION,
            "swe_version": ephemeris.swe_version(),
            "ephemeris_mode": ephemeris.ephe_mode(),
        },
        "lagna": {
            "ascendant": _r(houses.ascendant),
            "midheaven": _r(houses.midheaven),
            "sign": C.SIGNS[int(houses.ascendant // 30)],
            "sign_index": int(houses.ascendant // 30),
            "kp": _kp_dict(houses.ascendant),
        },
        "grahas": graha_out,
        "houses": houses_out,
        "significators": {"by_planet": psig, "by_house": hsig},
        "vargas": varga_mod.compute_vargas(grahas),
        "dasha": dasha,
    }


def chart_to_json(chart: dict) -> str:
    """Deterministic, key-sorted JSON serialization (FR-3.4)."""
    return json.dumps(chart, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
