"""The month calendar on Today: each day's tithi and nakshatra at sunrise, the Hindu festivals and Ekadashis, and a
separate Nanakshahi (Sikh) layer with Sangrand, Pooranmashi, Masya and the Gurpurabs.

Lunar days are read at local sunrise (sunset for the evening festivals), like the rest of the panchang. Months are
amanta internally (named by the Sun's sign at the new moon, app.muhurat_rules.lunar_month); ``style="purnimanta"``
renames the Krishna half after the following month, the North Indian way. Festival placement follows common Drik
practice in its simplest form; where schools differ we pick one rule and the screen says dates are to be checked.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import swisseph as swe

from app.muhurat_rules import lunar_month
from app.panchang_extra import LUNAR_MONTHS, SAMVATSARA, tithi_name
from core import constants as C
from core.ephemeris import julian_day, set_sidereal_mode
from core.panchang import _sidereal_sun_moon, compute_panchang

RASHI = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrishchika", "Dhanu", "Makara",
         "Kumbha", "Meena"]
# Ekadashi names: Shukla by amanta month; Krishna by purnimanta month (amanta month + 1).
EKADASHI_SHUKLA = ["Kamada", "Mohini", "Nirjala", "Devshayani", "Shravana Putrada", "Parivartini", "Papankusha",
                   "Dev Uthani", "Mokshada", "Pausha Putrada", "Jaya", "Amalaki"]
EKADASHI_KRISHNA = ["Papmochani", "Varuthini", "Apara", "Yogini", "Kamika", "Aja", "Indira", "Rama", "Utpanna",
                    "Saphala", "Shattila", "Vijaya"]
# (amanta month 0 = Chaitra, tithi 1..30): kept on the day the tithi runs at sunrise.
AT_SUNRISE = {
    (0, 1): "Chaitra Navratri begins · Ugadi, Gudi Padwa", (0, 9): "Ram Navami", (0, 15): "Hanuman Jayanti",
    (1, 3): "Akshaya Tritiya", (3, 15): "Guru Purnima", (4, 5): "Nag Panchami", (4, 15): "Raksha Bandhan",
    (4, 23): "Krishna Janmashtami", (6, 1): "Sharad Navratri begins", (7, 1): "Govardhan Puja", (7, 2): "Bhai Dooj", (7, 6): "Chhath Puja",
    (7, 15): "Kartik Purnima", (10, 5): "Vasant Panchami", (11, 16): "Holi",
}
# Kept when the tithi runs at a set part of the day: a fraction of sunrise→sunset (1 = sunset; 0.5 midday for
# Ganesh Chaturthi, 0.7 the afternoon for Dussehra), or "night" (midnight, for Shivaratri).
AT_MOMENT = {
    (6, 15): ("Sharad Purnima", 1), (6, 19): ("Karva Chauth", 1), (6, 28): ("Dhanteras", 1),
    (6, 30): ("Diwali · Lakshmi Puja", 1), (11, 15): ("Holika Dahan", "pradosh"), (5, 4): ("Ganesh Chaturthi", 0.5),
    (6, 10): ("Dussehra", 0.7), (10, 29): ("Maha Shivaratri", "night"),
}
PRADOSH_DAY = {"Sunday": "Ravi", "Monday": "Soma", "Tuesday": "Bhauma", "Wednesday": "Budha", "Thursday": "Guru",
               "Friday": "Shukra", "Saturday": "Shani"}
# Sikh days kept on lunar dates by both calendars (the 2003 Nanakshahi kept these three lunar too).
SIKH_LUNAR_BOTH = {(7, 15): "Prakash Purab, Guru Nanak Dev Ji", (11, 16): "Hola Mohalla"}
SIKH_SUNSET_BOTH = {(6, 30): "Bandi Chhor Divas"}
# The SGPC jantri's lunar Gurpurabs (sudi = Shukla, vadi = Krishna).
SIKH_LUNAR_SGPC = {
    (9, 7): "Prakash Purab, Guru Gobind Singh Ji", (2, 4): "Shaheedi Purab, Guru Arjan Dev Ji",
    (8, 5): "Shaheedi Purab, Guru Tegh Bahadur Ji", (7, 2): "Gurgaddi Divas, Guru Granth Sahib Ji",
    (6, 17): "Prakash Purab, Guru Ram Das Ji",
}
# The original (2003) Nanakshahi calendar's fixed solar dates for the same days.
SIKH_FIXED_ORIGINAL = {
    (1, 5): "Prakash Purab, Guru Gobind Singh Ji", (4, 14): "Vaisakhi · Khalsa Sajna Divas",
    (6, 16): "Shaheedi Purab, Guru Arjan Dev Ji", (10, 9): "Prakash Purab, Guru Ram Das Ji",
    (10, 20): "Gurgaddi Divas, Guru Granth Sahib Ji", (11, 24): "Shaheedi Purab, Guru Tegh Bahadur Ji",
}
# Nanakshahi solar months by the Sun's sidereal sign (Sangrand = the Sun entering it), and the original
# calendar's fixed first days (Gregorian month, day).
NS_MONTHS = ["Vaisakh", "Jeth", "Harh", "Sawan", "Bhadon", "Assu", "Katik", "Maghar", "Poh", "Magh", "Phagun", "Chet"]
NS_FIXED_START = [(4, 14), (5, 15), (6, 15), (7, 16), (8, 16), (9, 15), (10, 15), (11, 14), (12, 14), (1, 13),
                  (2, 12), (3, 14)]
TARA = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyak", "Sadhana", "Naidhana", "Mitra", "Param Mitra"]
TARA_GOOD, TARA_HARD = {1, 3, 5, 7, 8}, {2, 4, 6}


def _sun(jd: float) -> float:
    """The Sun's Lahiri longitude, as published panchangs time their Sankrantis."""
    set_sidereal_mode("lahiri")
    return swe.calc_ut(jd, swe.SUN, swe.FLG_MOSEPH | swe.FLG_SIDEREAL)[0][0] % 360.0


def _ingress(lo: float, hi: float) -> float:
    """The moment between Julian days lo and hi when the Sun changes sign."""
    s0 = int(_sun(lo) // 30)
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if int(_sun(mid) // 30) == s0 else (lo, mid)
    return hi


def _tithi(jd: float) -> int:
    s, m = _sidereal_sun_moon(jd)
    return int(((m - s) % 360) // 12) + 1


def _bhadra(jd: float) -> bool:
    """Bhadra (Vishti karana) running at this moment."""
    s, m = _sidereal_sun_moon(jd)
    return C.karana_name(int(((m - s) % 360) // 6)) == "Vishti"


def _hits(t0: int, t1: int, target: int) -> bool:
    """The tithi runs at this sunrise, or begins and ends between this sunrise and the next (kshaya)."""
    return t0 == target or ((target - t0) % 30 == 1 and (t1 - target) % 30 == 1)


def _ns_year(d: date) -> int:
    return d.year - (1468 if (d.month, d.day) >= (3, 14) else 1469)


def _ns_original(d: date) -> dict:
    """Month and day in the original Nanakshahi calendar (fixed Gregorian month starts)."""
    for i in range(12):
        m, day = NS_FIXED_START[i]
        start = date(d.year if (m, day) <= (d.month, d.day) else d.year - 1, m, day)
        nxt_m, nxt_d = NS_FIXED_START[(i + 1) % 12]
        end = date(start.year + (1 if (nxt_m, nxt_d) < (m, day) else 0), nxt_m, nxt_d)
        if start <= d < end:
            return {"month": NS_MONTHS[i], "day": (d - start).days + 1, "year": _ns_year(d), "start": start.isoformat()}
    raise AssertionError(d)


def _month(year: int, month: int, lat: float, lon: float, tz_name: str) -> tuple:
    from core.panchang import _AYANAMSHA
    return _month_cached(year, month, lat, lon, tz_name, _AYANAMSHA.get())


@lru_cache(maxsize=64)
def _month_cached(year: int, month: int, lat: float, lon: float, tz_name: str, ayanamsha: str) -> tuple:
    """One month of days; ``ayanamsha`` is only part of the cache key (the panchang reads it from core.panchang)."""
    tz = ZoneInfo(tz_name)
    first = date(year, month, 1)
    n = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - first).days
    ps = [compute_panchang(first + timedelta(days=i), lat, lon, tz_name) for i in range(-1, n + 1)]
    midnight = lambda d: julian_day(datetime(d.year, d.month, d.day, tzinfo=tz))  # noqa: E731
    days, seen, carry = [], set(), []
    for k in range(1, n + 1):
        p, nxt = ps[k], ps[k + 1]
        jd_rise, jd_set = julian_day(p.sunrise), julian_day(p.sunset)
        t0, t1 = p.tithi_number, nxt.tithi_number
        am, adhik = lunar_month(jd_rise)
        am_next = lunar_month(julian_day(nxt.sunrise))[0]
        sun_m = int(_sun(jd_rise) // 30)
        lo, hi = midnight(p.date), midnight(p.date + timedelta(days=1))
        s_lo, s_hi = int(_sun(lo) // 30), int(_sun(hi) // 30)
        sankranti = None
        if s_lo != s_hi:
            at = _ingress(lo, hi)
            sankranti = {"sign": s_hi, "name": f"{RASHI[s_hi]} Sankranti",
                         "at": (datetime(2000, 1, 1, 12, tzinfo=ZoneInfo("UTC")) + timedelta(days=at - 2451545.0))
                         .astimezone(tz).isoformat(timespec="minutes")}
        hindu, sikh_both, sikh_sgpc = [], [], []

        def lunar(table: dict, out: list, t_now: int, t_next: int, kind: str, mon: int) -> None:
            for (m, t), name in table.items():
                if m == mon and not adhik and (kind, m, t) not in seen and _hits(t_now, t_next, t):
                    seen.add((kind, m, t))
                    out.append(name)

        # A kshaya Pratipada belongs to the month that starts after this sunrise.
        mon = am_next if t0 == 30 and t1 == 2 else am
        lunar(AT_SUNRISE, hindu, t0, t1, "rise", mon)
        lunar(SIKH_LUNAR_BOTH, sikh_both, t0, t1, "sb", mon)
        lunar(SIKH_LUNAR_SGPC, sikh_sgpc, t0, t1, "sg", mon)
        jd_next = julian_day(nxt.sunrise)
        moments = [((m, t), name, at, hindu, "at") for (m, t), (name, at) in AT_MOMENT.items()]
        moments += [((m, t), name, 1, sikh_both, "ssb") for (m, t), name in SIKH_SUNSET_BOTH.items()]
        # Pradosh Vrat: Trayodashi at sunset, in either half; named for the weekday (Shukra Pradosh on a Friday)
        tset = _tithi(jd_set)
        if tset in (13, 28) and ("pradosh", am, tset) not in seen:
            seen.add(("pradosh", am, tset))
            hindu.append(f"{PRADOSH_DAY[p.weekday]} Pradosh Vrat")
        if carry:  # Holika Dahan moved here from yesterday's Bhadra evening
            hindu.append(carry.pop())
        for (m, t), name, at, out, kind in moments:
            jd = (jd_set + jd_next) / 2 if at == "night" else jd_set if at == "pradosh" else jd_rise + (jd_set - jd_rise) * at
            if (kind, m, t) not in seen and not adhik and _tithi(jd) == t and lunar_month(jd)[0] == m:
                seen.add((kind, m, t))
                if at == "pradosh" and _bhadra(jd):
                    carry.append(name)  # Holika is never lit in Bhadra: the next evening, as Drik Panchang has it
                else:
                    out.append(name)
        ek = next((t for t in (11, 26) if _hits(t0, t1, t) and ("ek", mon, t) not in seen), None)
        if ek and not adhik:
            seen.add(("ek", mon, ek))
            hindu.insert(0, f"{EKADASHI_SHUKLA[mon] if ek == 11 else EKADASHI_KRISHNA[(mon + 1) % 12]} Ekadashi")
        if sankranti:
            hindu.append(sankranti["name"])
        elif s_hi != 9 and int(_sun(midnight(p.date + timedelta(days=2))) // 30) == 9:
            hindu.append("Lohri")  # the eve of Makara Sankranti
        # ns_sign, the Sun's sign at the end of the day, names the SGPC (astronomical) Nanakshahi month.
        days.append({
            "date": p.date.isoformat(), "weekday": p.weekday, "tithi": t0, "tithi_name": tithi_name(t0),
            "paksha": p.paksha, "nakshatra": p.nakshatra, "nakshatra_index": p.nakshatra_index,
            "moon_sign": p.moon_sign_index, "amanta": am, "adhik": adhik, "sun_sign": sun_m, "ns_sign": s_hi,
            "sunrise": p.sunrise.astimezone(tz).isoformat(timespec="minutes"),
            "sunset": p.sunset.astimezone(tz).isoformat(timespec="minutes"),
            "yoga": p.yoga, "karana": p.karana,
            "rahu_kalam": [x.astimezone(tz).isoformat(timespec="minutes") for x in p.rahu_kalam],
            "sankranti": sankranti, "hindu": hindu, "sikh_both": sikh_both, "sikh_sgpc": sikh_sgpc,
        })
    return tuple(days)


def _sangrand_before(d: date, sign: int, tz: ZoneInfo) -> date:
    """The local date the Sun entered ``sign`` (the SGPC month's first day) on or before ``d``."""
    jd = julian_day(datetime(d.year, d.month, d.day, 23, 59, tzinfo=tz))
    back = (_sun(jd) - sign * 30) % 30
    lo = jd - back / 0.95 - 1.5
    at = _ingress(lo, jd) if int(_sun(lo) // 30) != sign else jd
    t = datetime(2000, 1, 1, 12, tzinfo=ZoneInfo("UTC")) + timedelta(days=at - 2451545.0)
    return t.astimezone(tz).date()


def month_view(year: int, month: int, lat: float, lon: float, tz_name: str, style: str = "purnimanta",
               nanakshahi: str = "sgpc", birth_nakshatra: int | None = None,
               birth_moon_sign: int | None = None) -> dict:
    tz = ZoneInfo(tz_name)
    base = _month(year, month, round(lat, 3), round(lon, 3), tz_name)
    sangrand: dict[int, date] = {}
    out = []
    for b in base:
        d = date.fromisoformat(b["date"])
        krishna = b["tithi"] > 15
        name_idx = (b["amanta"] + 1) % 12 if style == "purnimanta" and krishna else b["amanta"]
        lunar = ("Adhik " if b["adhik"] else "") + LUNAR_MONTHS[name_idx]
        if nanakshahi == "original":
            ns = _ns_original(d)
            sikh = list(b["sikh_both"]) + ([SIKH_FIXED_ORIGINAL[(d.month, d.day)]]
                                          if (d.month, d.day) in SIKH_FIXED_ORIGINAL else [])
            if ns["day"] == 1:
                sikh.insert(0, f"1 {ns['month']} · month begins")
        else:
            sign = b["ns_sign"]
            if sign not in sangrand:
                sangrand[sign] = _sangrand_before(d, sign, tz)
            start = sangrand[sign]
            ns = {"month": NS_MONTHS[sign], "day": (d - start).days + 1, "year": _ns_year(d),
                  "start": start.isoformat()}
            sikh = list(b["sikh_both"]) + list(b["sikh_sgpc"])
            if b["sankranti"]:
                sikh.insert(0, f"Sangrand · {NS_MONTHS[b['sankranti']['sign']]} begins")
                if b["sankranti"]["sign"] == 0:
                    sikh.append("Vaisakhi · Khalsa Sajna Divas")
        if b["tithi"] == 15:
            sikh.append("Pooranmashi")
        elif b["tithi"] == 30:
            sikh.append("Masya")
        day = {**b, "lunar_month": lunar, "nanakshahi": ns, "sikh": sikh}
        for k in ("sikh_both", "sikh_sgpc", "ns_sign"):
            day.pop(k)
        if birth_nakshatra is not None:
            t = ((b["nakshatra_index"] - birth_nakshatra) % 27) % 9
            day["tara"] = {"name": TARA[t], "kind": "good" if t in TARA_GOOD else "hard" if t in TARA_HARD else "janma"}
        if birth_moon_sign is not None:
            day["chandrashtama"] = b["moon_sign"] == (birth_moon_sign + 7) % 12
        out.append(day)
    mid = date(year, month, 15)
    am_mid = base[14]["amanta"]
    lunar_year = year - (1 if month <= 4 and am_mid >= 8 else 0)
    return {
        "year": year, "month": month, "tz_name": tz_name, "style": style, "nanakshahi": nanakshahi,
        "vikram_samvat": lunar_year + 57, "samvatsara": SAMVATSARA[(lunar_year - 1987) % 60],
        "nanakshahi_year": _ns_year(mid), "days": out,
    }
