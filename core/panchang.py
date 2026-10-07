"""Panchang: tithi, nakshatra, yoga, karana, sunrise/sunset and day windows.

Elements are stated at local sunrise, the traditional start of the Vedic day.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from core import constants as C
from core.ephemeris import julian_day, set_sidereal_mode

_RISE_FLAGS = swe.FLG_MOSEPH


@dataclass(frozen=True)
class Panchang:
    date: date
    tz: ZoneInfo
    weekday: str
    sunrise: datetime          # UTC
    sunset: datetime           # UTC
    tithi_number: int          # 1..30
    tithi_paksha_index: int    # 1..15 within paksha
    paksha: str                # 'Shukla' | 'Krishna'
    nakshatra_index: int       # 0..26
    nakshatra: str
    nakshatra_lord: str
    yoga_number: int           # 1..27
    yoga: str
    karana_number: int         # 1..60
    karana: str
    rahu_kalam: tuple[datetime, datetime]
    yamaganda: tuple[datetime, datetime]
    gulika: tuple[datetime, datetime]
    moon_sign_index: int = 0  # sidereal sign of the Moon at sunrise


def _jd_to_utc(jd: float) -> datetime:
    y, m, d, hour = swe.revjul(jd)
    return datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=hour)


def _event(jd_start: float, body: int, rsmi: int, lat: float, lon: float) -> float:
    retflag, tret = swe.rise_trans(jd_start, body, rsmi, (lon, lat, 0.0), 0.0, 0.0, _RISE_FLAGS)
    return tret[0]


def _sidereal_sun_moon(jd: float) -> tuple[float, float]:
    set_sidereal_mode("krishnamurti")
    flags = swe.FLG_MOSEPH | swe.FLG_SIDEREAL
    sun = swe.calc_ut(jd, swe.SUN, flags)[0][0] % 360.0
    moon = swe.calc_ut(jd, swe.MOON, flags)[0][0] % 360.0
    return sun, moon


def _window(sunrise: datetime, seg: timedelta, segment_index_1based: int) -> tuple[datetime, datetime]:
    start = sunrise + seg * (segment_index_1based - 1)
    return start, start + seg


def compute_panchang(d: date, lat: float, lon: float, tz_name: str) -> Panchang:
    tz = ZoneInfo(tz_name)
    local_midnight = datetime(d.year, d.month, d.day, tzinfo=tz)
    jd_midnight = julian_day(local_midnight)

    sunrise_jd = _event(jd_midnight, swe.SUN, swe.CALC_RISE, lat, lon)
    sunset_jd = _event(sunrise_jd, swe.SUN, swe.CALC_SET, lat, lon)
    sunrise = _jd_to_utc(sunrise_jd)
    sunset = _jd_to_utc(sunset_jd)

    sun_lon, moon_lon = _sidereal_sun_moon(sunrise_jd)
    elong = (moon_lon - sun_lon) % 360.0

    tithi_number = int(elong // 12.0) + 1
    paksha = "Shukla" if tithi_number <= 15 else "Krishna"
    tithi_paksha_index = tithi_number if tithi_number <= 15 else tithi_number - 15

    nak_index = int(moon_lon // C.NAKSHATRA_ARC)
    yoga_index0 = int(((sun_lon + moon_lon) % 360.0) // C.NAKSHATRA_ARC)
    karana_index0 = int(elong // 6.0)

    # Vedic weekday at local sunrise (Sunday = 0).
    py_wd = sunrise.astimezone(tz).weekday()  # Monday=0..Sunday=6
    vedic_wd = (py_wd + 1) % 7
    weekday = C.WEEKDAY_NAMES[vedic_wd]

    seg = (sunset - sunrise) / 8
    return Panchang(
        date=d,
        tz=tz,
        weekday=weekday,
        sunrise=sunrise,
        sunset=sunset,
        tithi_number=tithi_number,
        tithi_paksha_index=tithi_paksha_index,
        paksha=paksha,
        nakshatra_index=nak_index,
        nakshatra=C.NAKSHATRAS[nak_index],
        nakshatra_lord=C.NAKSHATRA_LORDS[nak_index],
        yoga_number=yoga_index0 + 1,
        yoga=C.YOGAS[yoga_index0],
        karana_number=karana_index0 + 1,
        karana=C.karana_name(karana_index0),
        rahu_kalam=_window(sunrise, seg, C.RAHU_KALAM_SEGMENT[vedic_wd]),
        yamaganda=_window(sunrise, seg, C.YAMAGANDA_SEGMENT[vedic_wd]),
        gulika=_window(sunrise, seg, C.GULIKA_SEGMENT[vedic_wd]),
        moon_sign_index=int(moon_lon // 30.0),
    )
