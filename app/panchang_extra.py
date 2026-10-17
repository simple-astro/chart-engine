"""The fuller panchang for the Muhurat screen: when each limb ends, the hora, lords and deities, the year, month,
season and naming letters. Kept apart from the muhurat rules; only the Muhurat screen asks for it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import constants as C
from core.ephemeris import julian_day
from core.panchang import _sidereal_sun_moon

ARC = C.NAKSHATRA_ARC
NAKSHATRA_DEITY = ["Ashwini Kumaras", "Yama", "Agni", "Brahma", "Soma", "Rudra", "Aditi", "Brihaspati", "Sarpas",
                   "Pitrs", "Bhaga", "Aryaman", "Savitr", "Vishwakarma", "Vayu", "Indra and Agni", "Mitra", "Indra",
                   "Nirriti", "Apa", "Vishvedevas", "Vishnu", "Vasus", "Varuna", "Aja Ekapada", "Ahir Budhnya", "Pushan"]
TITHI_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]  # 1st..8th, then again
TITHI_DEITY = ["Agni", "Brahma", "Gauri", "Ganesha", "Nagas", "Kartikeya", "Surya", "Shiva", "Durga", "Yama",
               "Vishvedevas", "Vishnu", "Kamadeva", "Shiva", "Chandra"]  # Pratipada..Purnima; Amavasya: Pitrs
# Naming letters (the first sound of a name) for each pada of each nakshatra.
NAMING = ["Chu Che Cho La", "Li Lu Le Lo", "A I U E", "O Va Vi Vu", "Ve Vo Ka Ki", "Ku Gha Ng Chha", "Ke Ko Ha Hi",
          "Hu He Ho Da", "Di Du De Do", "Ma Mi Mu Me", "Mo Ta Ti Tu", "Te To Pa Pi", "Pu Sha Na Tha", "Pe Po Ra Ri",
          "Ru Re Ro Ta", "Ti Tu Te To", "Na Ni Nu Ne", "No Ya Yi Yu", "Ye Yo Bha Bhi", "Bhu Dha Pha Dha",
          "Bhe Bho Ja Ji", "Ju Je Jo Gha", "Ga Gi Gu Ge", "Go Sa Si Su", "Se So Da Di", "Du Tha Jha Na",
          "De Do Cha Chi"]
LUNAR_MONTHS = ["Chaitra", "Vaishakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada", "Ashwayuja", "Kartika",
                "Margashira", "Pausha", "Magha", "Phalguna"]
RITU = ["Vasanta (spring)", "Grishma (summer)", "Varsha (monsoon)", "Sharad (autumn)", "Hemanta (early winter)",
        "Shishira (late winter)"]
SAMVATSARA = ["Prabhava", "Vibhava", "Shukla", "Pramoduta", "Prajotpatti", "Angirasa", "Shrimukha", "Bhava", "Yuva",
              "Dhatu", "Ishvara", "Bahudhanya", "Pramathi", "Vikrama", "Vrisha", "Chitrabhanu", "Svabhanu", "Tarana",
              "Parthiva", "Vyaya", "Sarvajit", "Sarvadhari", "Virodhi", "Vikriti", "Khara", "Nandana", "Vijaya",
              "Jaya", "Manmatha", "Durmukhi", "Hevilambi", "Vilambi", "Vikari", "Sharvari", "Plava", "Shubhakrit",
              "Shobhakrit", "Krodhi", "Vishvavasu", "Parabhava", "Plavanga", "Kilaka", "Saumya", "Sadharana",
              "Virodhikrit", "Paridhavi", "Pramadi", "Ananda", "Rakshasa", "Nala", "Pingala", "Kalayukti",
              "Siddharthi", "Raudri", "Durmati", "Dundubhi", "Rudhirodgari", "Raktakshi", "Krodhana", "Akshaya"]
SYNODIC = 360 / 29.530589  # mean elongation per day


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def tithi_name(n: int) -> str:
    """n = 1..30 (1..15 Shukla, 16..30 Krishna)."""
    if n == 15:
        return "Purnima"
    if n == 30:
        return "Amavasya"
    return f"{'Shukla' if n <= 15 else 'Krishna'} {_ordinal(n if n <= 15 else n - 15)}"


def _at(jd: float) -> tuple[float, float]:
    return _sidereal_sun_moon(jd)


def _index(kind: str, jd: float) -> int:
    s, m = _at(jd)
    e = (m - s) % 360
    return {"tithi": int(e // 12), "nakshatra": int(m // ARC), "yoga": int(((s + m) % 360) // ARC),
            "karana": int(e // 6)}[kind]


def _utc(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def _name(kind: str, i: int) -> str:
    if kind == "tithi":
        return tithi_name(i + 1)
    if kind == "nakshatra":
        return C.NAKSHATRAS[i % 27]
    if kind == "yoga":
        return C.YOGAS[i % 27]
    return C.karana_name(i % 60)


def limb_ends(sunrise: datetime) -> dict:
    """When the tithi, nakshatra, yoga and karana running at sunrise end, and what comes next."""
    jd0 = julian_day(sunrise)
    out = {}
    for kind in ("tithi", "nakshatra", "yoga", "karana"):
        i0, lo, hi = _index(kind, jd0), jd0, jd0
        for _ in range(48):  # hour steps: every limb ends within about a day and a half
            hi += 1 / 24
            if _index(kind, hi) != i0:
                break
        for _ in range(14):  # to within a second or so
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _index(kind, mid) == i0 else (lo, mid)
        nxt = _index(kind, hi)
        out[kind] = {"name": _name(kind, i0), "ends": _utc(hi).isoformat(timespec="seconds"), "next": _name(kind, nxt)}
    return out


def _last_new_moon(jd: float) -> float:
    s, m = _at(jd)
    t = jd - ((m - s) % 360) / SYNODIC
    for _ in range(3):
        s, m = _at(t)
        t -= (((m - s) + 180) % 360 - 180) / SYNODIC
    return t


def details(p, next_sunrise: datetime) -> dict:
    """Hora list, lords and deities, the year, lunar and solar month, season and naming letters for the day of
    Panchang ``p`` (all at sunrise)."""
    from app.today import horas  # local import: app.today imports app.muhurat
    jd = julian_day(p.sunrise)
    s, m = _at(jd)
    nak, tithi = int(m // ARC), p.tithi_number
    month = (int(_at(_last_new_moon(jd))[0] // 30) + 1) % 12  # amanta: named by the Sun's sign at the new moon
    year = p.date.year - (1 if p.date.month <= 4 and month >= 8 else 0)  # the lunar year starts in Chaitra
    pada = int((m % ARC) // (ARC / 4))
    letters = NAMING[nak].split()
    return {
        "horas": horas(p, next_sunrise),
        "nakshatra_lord": C.NAKSHATRA_LORDS[nak], "nakshatra_deity": NAKSHATRA_DEITY[nak],
        "tithi_lord": TITHI_LORD[(tithi - 1) % 8] if tithi != 30 else "Rahu",
        "tithi_deity": "Pitrs" if tithi == 30 else TITHI_DEITY[(tithi - 1) % 15],
        "samvatsara": SAMVATSARA[(year - 1987) % 60],
        "lunar_month": LUNAR_MONTHS[month], "solar_month": C.SIGNS[int(s // 30)], "ritu": RITU[month // 2],
        "naming": {"letters": letters, "pada": pada + 1, "now": letters[pada]},
    }
