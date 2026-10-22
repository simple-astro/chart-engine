"""Uranus, Neptune and Pluto, for astrologers who like to see them.

They are kept apart from the nine grahas: no Vedic table (dignity, Shadbala, Ashtakavarga, dashas, yogas) uses
them, so they are shown on the chart and in the planet table only, as an optional extra.
"""
from __future__ import annotations

from types import SimpleNamespace

import swisseph as swe

from core import constants as C
from core.ephemeris import sidereal_longitude
from core.grahas import _nakshatra_of
from core.kp import kp_lords, planet_house

OUTER = {"Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO}


def outer_planets(chart: dict) -> dict:
    jd, ayan = chart["meta"]["julian_day"], chart["meta"]["ayanamsha"]
    cusps = SimpleNamespace(cusps=[SimpleNamespace(house=h["house"], longitude=h["longitude"]) for h in chart["houses"]])
    out = {}
    for name, pid in OUTER.items():
        lon, speed = sidereal_longitude(jd, pid, ayan)
        lon %= 360.0
        si = int(lon // 30)
        n_idx, n_name, n_lord, pada = _nakshatra_of(lon)
        k = kp_lords(lon)
        out[name] = {
            "longitude": round(lon, 6), "speed": round(speed, 6), "sign": C.SIGNS[si], "sign_index": si,
            "sign_lord": C.SIGN_LORDS[si],
            "degrees_in_sign": round(lon % 30, 6), "nakshatra": n_name, "nakshatra_index": n_idx,
            "nakshatra_lord": n_lord, "pada": pada, "retrograde": speed < 0,
            "house": planet_house(lon, cusps),
            "kp": {"sign_lord": k.sign_lord, "star_lord": k.star_lord, "sub_lord": k.sub_lord,
                   "sub_sub_lord": k.sub_sub_lord},
        }
    return out
