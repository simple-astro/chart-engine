"""Hard exclusions for muhurat: days a tradition rules out for an activity whatever the rest of the panchang says.

Each rule is one entry in RULES; ACTIVITY_RULES says which rules apply to which activity. The set below follows the
common North Indian (Vaishnava / Drik panchang) practice for weddings. Schools differ (e.g. whether Dev Uthani
Ekadashi itself is open, the orbs for Guru and Shukra asta), so change the lists here rather than the code.

Lunar months are amanta (new moon to new moon), named by the sign the Sun enters during the month; a month in which
the Sun enters no sign is Adhik (extra). Everything is read at local sunrise, like the rest of the panchang.
"""
from __future__ import annotations

import swisseph as swe

from core import constants as C
from core.ephemeris import julian_day
from core.panchang import _sidereal_sun_moon

SYNODIC = 29.530589
CHAITRA, ASHADHA, SHRAVANA, BHADRAPADA, ASHWAYUJA, KARTIKA, PHALGUNA = 0, 3, 4, 5, 6, 7, 11
SAGITTARIUS, PISCES = 8, 11

# Rule key -> the reason shown to the user when it excludes a day.
RULES = {
    "rikta": "Rikta (empty) tithi: avoided for weddings",
    "ashtami": "Ashtami tithi: avoided for weddings",
    "amavasya": "Amavasya (new moon): avoided for weddings",
    "chaturmas": "Chaturmas: weddings are traditionally avoided (Devshayani to Dev Uthani Ekadashi)",
    "adhik": "Adhik Maas (extra lunar month): weddings are traditionally avoided",
    "pitru_paksha": "Pitru Paksha: a time for the ancestors, weddings are avoided",
    "kharmas": "Kharmas (Sun in Sagittarius or Pisces): weddings are traditionally avoided",
    "holashtak": "Holashtak (8 days before Holi): weddings are traditionally avoided",
    "guru_asta": "Guru asta (Jupiter combust, too close to the Sun): weddings are avoided",
    "shukra_asta": "Shukra asta (Venus combust, too close to the Sun): weddings are avoided",
}
ACTIVITY_RULES = {
    "marriage": ("rikta", "ashtami", "amavasya", "chaturmas", "adhik", "pitru_paksha", "kharmas", "holashtak",
                 "guru_asta", "shukra_asta"),
}
# Chaturmas ends on Dev Uthani (Prabodhini) Ekadashi, Kartika Shukla 11. Many families hold weddings from that day
# (Tulsi vivah); set True to keep the Ekadashi itself closed too.
CHATURMAS_END_INCLUSIVE = False
ASTA_ORB = {"Jupiter": C.COMBUSTION_ORB["Jupiter"], "Venus": C.COMBUSTION_ORB["Venus"]}


def _sun(jd: float) -> float:
    return _sidereal_sun_moon(jd)[0]


def _new_moon_near(t: float) -> float:
    """Refine a guess to the exact new moon (Sun and Moon at the same longitude)."""
    for _ in range(4):
        s, m = _sidereal_sun_moon(t)
        t -= (((m - s) + 180) % 360 - 180) / (360 / SYNODIC)
    return t


def lunar_month(jd: float) -> tuple[int, bool]:
    """(amanta month index 0 = Chaitra .. 11 = Phalguna, adhik?) for the lunar month running at Julian day ``jd``."""
    s, m = _sidereal_sun_moon(jd)
    start = _new_moon_near(jd - ((m - s) % 360) / (360 / SYNODIC))
    end = _new_moon_near(start + SYNODIC)
    s0, s1 = int(_sun(start) // 30), int(_sun(end) // 30)
    return (s0 + 1) % 12, s0 == s1


def _separation(jd: float, planet: int, sun: float) -> float:
    lon = swe.calc_ut(jd, planet, swe.FLG_MOSEPH | swe.FLG_SIDEREAL)[0][0] % 360.0
    return abs((lon - sun + 180) % 360 - 180)


def facts(p) -> dict:
    """The calendar facts at sunrise that the rules read."""
    jd = julian_day(p.sunrise)
    sun = _sun(jd)
    month, adhik = lunar_month(jd)
    return {"tithi": p.tithi_number, "paksha_index": p.tithi_paksha_index, "month": month, "adhik": adhik,
            "sun_sign": int(sun // 30),
            "jupiter_sep": _separation(jd, swe.JUPITER, sun), "venus_sep": _separation(jd, swe.VENUS, sun)}


def _chaturmas(month: int, tithi: int) -> bool:
    if month == ASHADHA:
        return tithi >= 11              # from Devshayani Ekadashi (Ashadha Shukla 11)
    if month in (SHRAVANA, BHADRAPADA, ASHWAYUJA):
        return True
    if month == KARTIKA:
        return tithi < 11 or (CHATURMAS_END_INCLUSIVE and tithi == 11)  # to Dev Uthani Ekadashi (Kartika Shukla 11)
    return False


CHECKS = {
    "rikta": lambda f: f["tithi"] != 30 and f["paksha_index"] in (4, 9, 14),
    "ashtami": lambda f: f["paksha_index"] == 8,
    "amavasya": lambda f: f["tithi"] == 30,
    "chaturmas": lambda f: not f["adhik"] and _chaturmas(f["month"], f["tithi"]),
    "adhik": lambda f: f["adhik"],
    "pitru_paksha": lambda f: not f["adhik"] and f["month"] == BHADRAPADA and f["tithi"] >= 16,
    "kharmas": lambda f: f["sun_sign"] in (SAGITTARIUS, PISCES),
    "holashtak": lambda f: not f["adhik"] and f["month"] == PHALGUNA and 8 <= f["tithi"] <= 15,
    "guru_asta": lambda f: f["jupiter_sep"] <= ASTA_ORB["Jupiter"],
    "shukra_asta": lambda f: f["venus_sep"] <= ASTA_ORB["Venus"],
}


def exclusions(activity: str, f: dict | None) -> list[dict]:
    """The rules that rule this day out for ``activity``: [{key, reason}] (empty if none apply or no facts)."""
    if not f:
        return []
    return [{"key": k, "reason": RULES[k]} for k in ACTIVITY_RULES.get(activity, ()) if CHECKS[k](f)]
