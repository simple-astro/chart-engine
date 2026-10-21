"""Shadbala (six-fold planetary strength) and Bhava Bala (house strength), in virupas (60 = 1 rupa).

Brihat Parashara Hora Shastra ch. 27-28, calibrated against two printouts from the owner's desktop software
(Deepak Saluja 11 Mar 1978 03:10 Karnal; Sukhdeep 1 Sep 1987 14:20 Chandigarh), which every value below matches
unless noted:
- KP (Krishnamurti) ayanamsha; whole-sign houses for Kendra Bala; the ascendant and MC for Dig Bala; Sripati
  (Porphyry) cusps — each quadrant split in three — for the bhavas.
- Sthana: Uchcha, Saptavarga (D1 D2 D3 D7 D9 D12 D30; Moolatrikona counts only in D1; compound relationships from the
  birth chart), Ojayugma, Kendra, Drekkana.
- Kala: Nathonnatha from local mean time; Paksha with Mercury always benefic and the Moon given twice the malefic
  value; Tribhaga; Abda and Masa from the Kali epoch (365.2422-day years, 30-day months); Vara and Hora;
  Ayana from the classical 24° declination table (Sun doubled); Yuddha.
- Cheshta: BPHS v. 24 with Surya Siddhanta mean motions, (mean + true)/2 taken as a circular mean; the Sun and Moon
  get none (their motion is already in Ayana and Paksha Bala).
- Drik: sphuta drishti plus the special aspects of Mars, Jupiter and Saturn; benefics are Jupiter, Venus, Mercury and
  the waxing Moon; (benefic − malefic) / 4.
- Bhava: lord's Shadbala + Bhava Dig Bala (by the cusp's sign and half) + Bhava Drishti (Jupiter and Mercury in full,
  others quartered).
- A birth after midnight but before sunrise keeps the calendar weekday, as in the owner's software (BPHS would count
  the previous weekday): its Vara, Hora and Tribhaga lords follow that software.
Where the printouts differ from BPHS otherwise, this follows BPHS: in a planetary war the winner gains what the loser
loses (the printout adds it to both); the (mean + true)/2 of Cheshta is not thrown 180° when the two straddle 0° Aries.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from core.ephemeris import get_ayanamsha, julian_day
from core.grahas import compute_grahas
from core.houses import compute_houses
from core.panchang import compute_panchang

AYAN = "krishnamurti"
P = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
WEEKDAY_LORD = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
EXALT = {"Sun": 10, "Moon": 33, "Mars": 298, "Mercury": 165, "Jupiter": 95, "Venus": 357, "Saturn": 200}
MOOLA = {"Sun": (4, 0, 20), "Moon": (1, 3, 30), "Mars": (0, 0, 12), "Mercury": (5, 15, 20), "Jupiter": (8, 0, 10),
         "Venus": (6, 0, 15), "Saturn": (10, 0, 20)}
# Natural friends, neutrals (the rest are enemies).
NATURAL = {"Sun": ({"Moon", "Mars", "Jupiter"}, {"Mercury"}), "Moon": ({"Sun", "Mercury"}, {"Mars", "Jupiter", "Venus", "Saturn"}),
           "Mars": ({"Sun", "Moon", "Jupiter"}, {"Venus", "Saturn"}), "Mercury": ({"Sun", "Venus"}, {"Mars", "Jupiter", "Saturn"}),
           "Jupiter": ({"Sun", "Moon", "Mars"}, {"Saturn"}), "Venus": ({"Mercury", "Saturn"}, {"Mars", "Jupiter"}),
           "Saturn": ({"Mercury", "Venus"}, {"Jupiter"})}
COMPOUND_PTS = {2: 22.5, 1: 15.0, 0: 7.5, -1: 3.75, -2: 1.875}
NAISARGIKA = {"Sun": 60.0, "Moon": 51.43, "Mars": 17.14, "Mercury": 25.70, "Jupiter": 34.28, "Venus": 42.85, "Saturn": 8.57}
REQUIRED = {"Sun": 5.0, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0, "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0}  # rupas
DISC = {"Mars": 9.4, "Mercury": 6.6, "Jupiter": 190.4, "Venus": 16.6, "Saturn": 158.0}
KRANTI = [0, 362, 703, 1002, 1238, 1388, 1440]  # declination (arc-minutes) every 15° of sayana longitude, obliquity 24°
SS_DAYS, SS_REV = 1577917828, {"Sun": 4320000, "Mercury": 17937060, "Venus": 7022376, "Mars": 2296832,
                                "Jupiter": 364220, "Saturn": 146568}
KALI = 588465.5  # JD of the Kali Yuga epoch (18 Feb 3102 BCE)
IDS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
       "Venus": swe.VENUS, "Saturn": swe.SATURN}


def _fold(x: float) -> float:
    x %= 360
    return 360 - x if x > 180 else x


def _sign(lon: float) -> int:
    return int(lon % 360 // 30)


# ---------- Sthana Bala ----------
def varga_sign(lon: float, n: int) -> int:
    s, d = _sign(lon), lon % 30
    odd = s % 2 == 0
    if n == 1:
        return s
    if n == 2:
        return (4 if d < 15 else 3) if odd else (3 if d < 15 else 4)
    if n == 3:
        return (s + 4 * int(d // 10)) % 12
    if n == 7:
        k = int(d // (30 / 7))
        return (s + k) % 12 if odd else (s + 6 + k) % 12
    if n == 9:
        return int(lon % 360 // (10 / 3)) % 12
    if n == 12:
        return (s + int(d // 2.5)) % 12
    if n == 30:
        parts = [(5, 0), (10, 10), (18, 8), (25, 2), (30, 6)] if odd else [(5, 1), (12, 5), (20, 11), (25, 9), (30, 7)]
        return next(sg for lim, sg in parts if d < lim)
    raise ValueError(n)


def compound(p: str, q: str, signs: dict) -> int:
    nat = 1 if q in NATURAL[p][0] else 0 if q in NATURAL[p][1] else -1
    tat = 1 if (signs[q] - signs[p]) % 12 + 1 in (2, 3, 4, 10, 11, 12) else -1
    return nat + tat


def saptavarga(p: str, lon: dict) -> float:
    signs = {q: _sign(lon[q]) for q in P}
    total = 0.0
    for n in (1, 2, 3, 7, 9, 12, 30):
        sg = varga_sign(lon[p], n)
        ms, a, b = MOOLA[p]
        if n == 1 and sg == ms and a <= lon[p] % 30 < b:
            total += 45
        elif LORD[sg] == p:
            total += 30
        else:
            total += COMPOUND_PTS[compound(p, LORD[sg], signs)]
    return total


def sthana(p: str, lon: dict, lagna_sign: int) -> dict:
    uchcha = _fold(lon[p] - (EXALT[p] + 180)) / 3
    female = p in ("Moon", "Venus")
    oja = sum(15 for s in (_sign(lon[p]), varga_sign(lon[p], 9)) if (s % 2 == 1) == female)
    house = (_sign(lon[p]) - lagna_sign) % 12 + 1
    kendra = 60 if house in (1, 4, 7, 10) else 30 if house in (2, 5, 8, 11) else 15
    third = int(lon[p] % 30 // 10)
    drek = 15 if third == ({"Sun": 0, "Mars": 0, "Jupiter": 0, "Mercury": 1, "Saturn": 1}.get(p, 2)) else 0
    parts = {"uchcha": uchcha, "saptavarga": saptavarga(p, lon), "ojayugma": oja, "kendra": kendra, "drekkana": drek}
    return {**parts, "total": sum(parts.values())}


def dig(p: str, lon: dict, asc: float, mc: float) -> float:
    point = {"Sun": mc, "Mars": mc, "Jupiter": asc, "Mercury": asc, "Moon": mc + 180, "Venus": mc + 180,
             "Saturn": asc + 180}[p]
    return (180 - _fold(lon[p] - point)) / 3


# ---------- Kala Bala ----------
def kranti(sayana: float) -> float:
    l, s = sayana % 360, 1
    if l > 180:
        l, s = l - 180, -1
    if l > 90:
        l = 180 - l
    i = int(l // 15)
    v = KRANTI[i] + (KRANTI[min(i + 1, 6)] - KRANTI[i]) * (l - 15 * i) / 15
    return s * v / 60


def _kali_lord(jd: float, length: float, tz: ZoneInfo) -> str:
    start = KALI + math.floor((jd - KALI) / length) * length
    d = (datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=start - 2451545.0)).astimezone(tz)
    return WEEKDAY_LORD[(d.weekday() + 1) % 7]


def kala(when: datetime, lat: float, lon_e: float, lon: dict, wars: list) -> dict:
    jd = julian_day(when)
    tz = when.tzinfo
    utc = when.astimezone(timezone.utc)
    lmt = utc + timedelta(hours=lon_e / 15)
    hours = lmt.hour + lmt.minute / 60 + lmt.second / 3600
    from_midnight = hours if hours <= 12 else 24 - hours
    day_strong = from_midnight * 15 / 3  # 0 at midnight, 60 at noon
    elong = _fold(lon["Moon"] - lon["Sun"])
    ben_pk = elong / 3

    # The day is the calendar day, as in the owner's desktop software. A birth after midnight but before sunrise keeps
    # that calendar weekday (BPHS would still count the previous one), its hora is counted on from that day's sunrise
    # round the clock, and its third of the night is counted back from sunrise.
    local = when.astimezone(tz)
    p = compute_panchang(local.date(), lat, lon_e, tz.key)
    day_lord = WEEKDAY_LORD[(local.weekday() + 1) % 7]
    chaldean = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
    hora_lord = chaldean[(chaldean.index(day_lord) + int((utc - p.sunrise).total_seconds() % 86400 // 3600)) % 7]
    if utc < p.sunrise:
        prev = compute_panchang(local.date() - timedelta(days=1), lat, lon_e, tz.key)
        third = int(3 * (p.sunrise - utc) / (p.sunrise - prev.sunset))
        tri_lord = ["Moon", "Venus", "Mars"][min(third, 2)]
    elif utc < p.sunset:
        third = int(3 * (utc - p.sunrise) / (p.sunset - p.sunrise))
        tri_lord = ["Mercury", "Sun", "Saturn"][min(third, 2)]
    else:
        nxt = compute_panchang(local.date() + timedelta(days=1), lat, lon_e, tz.key)
        third = int(3 * (utc - p.sunset) / (nxt.sunrise - p.sunset))
        tri_lord = ["Moon", "Venus", "Mars"][min(third, 2)]
    abda, masa = _kali_lord(jd, 365.2422, tz), _kali_lord(jd, 30.0, tz)
    ayan = get_ayanamsha(jd, AYAN)

    out = {}
    for q in P:
        if q == "Mercury":
            nata = 60.0
        elif q in ("Sun", "Jupiter", "Venus"):
            nata = day_strong
        else:
            nata = 60 - day_strong
        paksha = ben_pk if q in ("Mercury", "Jupiter", "Venus") else 2 * (60 - ben_pk) if q == "Moon" else 60 - ben_pk
        d = kranti(lon[q] + ayan)
        ayana = (24 + d if q in ("Sun", "Mars", "Jupiter", "Venus") else 24 - d if q in ("Moon", "Saturn")
                 else 24 + abs(d)) / 48 * 60
        if q == "Sun":
            ayana *= 2
        parts = {"nathonnatha": nata, "paksha": paksha, "tribhaga": 60.0 if q in (tri_lord, "Jupiter") else 0.0,
                 "abda": 15.0 if q == abda else 0.0, "masa": 30.0 if q == masa else 0.0,
                 "vara": 45.0 if q == day_lord else 0.0, "hora": 60.0 if q == hora_lord else 0.0,
                 "ayana": ayana, "yuddha": 0.0}
        out[q] = parts
    for w in wars:
        out[w["winner"]]["yuddha"] += w["bala"]
        out[w["loser"]]["yuddha"] -= w["bala"]
    for q in P:
        out[q]["total"] = sum(v for k, v in out[q].items() if k != "total")
    return out


# ---------- Cheshta ----------
def _ss_mean(p: str, jd: float) -> float:
    return ((jd - KALI) * SS_REV[p] / SS_DAYS % 1) * 360


def _circ_mean(a: float, b: float) -> float:
    return (a + ((b - a + 180) % 360 - 180) / 2) % 360


def cheshta(q: str, jd: float, lon: dict) -> float:
    if q in ("Sun", "Moon"):
        return 0.0
    seeghra, mean = ((_ss_mean("Sun", jd), _ss_mean(q, jd)) if q in ("Mars", "Jupiter", "Saturn")
                     else (_ss_mean(q, jd), _ss_mean("Sun", jd)))
    return _fold(seeghra - _circ_mean(mean, lon[q])) / 3


# ---------- Drik ----------
def sphuta_drishti(k: float) -> float:
    k %= 360
    if k < 30 or k >= 300:
        return 0.0
    if k < 60:
        return (k - 30) / 2
    if k < 90:
        return k - 45
    if k < 120:
        return (120 - k) / 2 + 30
    if k < 150:
        return 150 - k
    if k < 180:
        return (k - 150) * 2
    return (300 - k) / 2


def drishti(p: str, k: float) -> float:
    k %= 360
    extra = (15 if p == "Mars" and (90 <= k < 120 or 210 <= k < 240) else
             30 if p == "Jupiter" and (120 <= k < 150 or 240 <= k < 270) else
             45 if p == "Saturn" and (60 <= k < 90 or 270 <= k < 300) else 0)
    return sphuta_drishti(k) + extra


def benefics(lon: dict) -> set:
    waxing = (lon["Moon"] - lon["Sun"]) % 360 < 180
    return {"Jupiter", "Venus", "Mercury"} | ({"Moon"} if waxing else set())


def drik(q: str, lon: dict) -> float:
    ben = benefics(lon)
    return sum((1 if p in ben else -1) * drishti(p, lon[q] - lon[p]) for p in P if p != q) / 4


# ---------- the whole ----------
def wars(jd: float, lon: dict, pre: dict) -> list:
    """Planets within 1° (Mars to Saturn). BPHS 27: the gap in strength (Sthana + Dig + Kala) over the gap in disc
    size goes to the winner and is taken from the loser; the planet further north wins."""
    lat = {p: swe.calc_ut(jd, IDS[p])[0][1] for p in DISC}
    out = []
    names = list(DISC)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _fold(lon[a] - lon[b]) < 1:
                win, lose = (a, b) if lat[a] > lat[b] else (b, a)
                bala = abs(pre[a] - pre[b]) / abs(DISC[a] - DISC[b])
                out.append({"planets": [a, b], "winner": win, "loser": lose, "bala": bala})
    return out


def sripati_cusps(asc: float, mc: float) -> list[float]:
    ic, dsc = (mc + 180) % 360, (asc + 180) % 360
    cusps = []
    for a, b in ((asc, ic), (ic, dsc), (dsc, mc), (mc, asc)):
        arc = (b - a) % 360
        cusps += [a, (a + arc / 3) % 360, (a + 2 * arc / 3) % 360]
    return cusps


def bhava_dig(cusp: float) -> float:
    s, d = _sign(cusp), cusp % 30
    if s in (2, 5, 6, 10) or (s == 8 and d < 15):
        strong = 1  # human signs
    elif s in (0, 1, 4) or (s == 8 and d >= 15) or (s == 9 and d < 15):
        strong = 10  # quadrupeds
    elif s in (3, 11) or (s == 9 and d >= 15):
        strong = 4  # watery
    else:
        strong = 7  # Scorpio
    return strong


def compute(when: datetime, lat: float, lon_e: float) -> dict:
    jd = julian_day(when)
    g = compute_grahas(jd, AYAN)
    lon = {p: g[p].longitude for p in P}
    h = compute_houses(jd, lat, lon_e, AYAN, "placidus")
    asc, mc = h.ascendant, h.midheaven
    lagna = _sign(asc)

    sth = {p: sthana(p, lon, lagna) for p in P}
    dg = {p: dig(p, lon, asc, mc) for p in P}
    k0 = kala(when, lat, lon_e, lon, [])
    pre = {p: sth[p]["total"] + dg[p] + k0[p]["total"] for p in DISC}
    war = wars(jd, lon, pre)
    kl = kala(when, lat, lon_e, lon, war) if war else k0
    planets = {}
    for p in P:
        c, d = cheshta(p, jd, lon), drik(p, lon)
        total = sth[p]["total"] + dg[p] + kl[p]["total"] + c + NAISARGIKA[p] + d
        ch_ishta = (kl["Sun"]["ayana"] / 2 if p == "Sun" else _fold(lon["Moon"] - lon["Sun"]) / 3 if p == "Moon"
                    else c)  # the Sun's and Moon's motion is their Ayana and (benefic) Paksha Bala
        u = sth[p]["uchcha"]
        planets[p] = {"sthana": sth[p], "dig": dg[p], "kala": kl[p], "cheshta": c, "naisargika": NAISARGIKA[p],
                      "drik": d, "total": total, "rupas": total / 60, "required": REQUIRED[p],
                      "ratio": total / 60 / REQUIRED[p], "ishta": math.sqrt(u * ch_ishta),
                      "kashta": math.sqrt((60 - u) * (60 - ch_ishta))}
    order = sorted(P, key=lambda p: -planets[p]["total"])  # ranked by total, as the owner's software does
    for p in P:
        planets[p]["rank"] = order.index(p) + 1

    cusps = sripati_cusps(asc, mc)
    ben = benefics(lon)
    bhavas = []
    for i, c in enumerate(cusps):
        lord = LORD[_sign(c)]
        strong = bhava_dig(c)
        dist = min((i + 1 - strong) % 12, (strong - i - 1) % 12)
        bdig = (6 - dist) * 10
        bdr = sum(drishti(p, c - lon[p]) * (1 if p in ("Jupiter", "Mercury") else (1 if p in ben else -1) / 4)
                  for p in P)
        total = planets[lord]["total"] + bdig + bdr
        bhavas.append({"house": i + 1, "cusp": c, "lord": lord, "adhipati": planets[lord]["total"], "dig": bdig,
                       "drishti": bdr, "total": total, "rupas": total / 60})
    border = sorted(range(12), key=lambda i: -bhavas[i]["total"])
    for i, b in enumerate(bhavas):
        b["rank"] = border.index(i) + 1
    return {"ayanamsha": AYAN, "planets": planets, "bhavas": bhavas, "wars": war}
