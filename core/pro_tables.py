"""Tables for the astrologers' Pro dashboard that the chart does not already carry.

Avasthas (Baladi by degree, Jagradadi by dignity), the three friendship tables (natural, temporary and fivefold),
Vimshopaka Bala for the 6, 7, 10 and 16-varga schemes, the Sun-based upagrahas (Dhuma to Upaketu), and every
Sade Sati and Saturn dhaiya of a life, counted from the natal Moon sign.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import swisseph as swe

from core.constants import SIGNS
from core.dignity import dignity
from core.ephemeris import julian_day, sidereal_longitude
from core.shadbala import LORD, MOOLA, NATURAL, P, compound

# ----- avasthas -----
BALADI = ["Bala (infant)", "Kumara (youth)", "Yuva (adult)", "Vriddha (old)", "Mrita (dead)"]


def baladi(sign: int, deg: float) -> str:
    """Five 6° parts: in odd signs Bala first, in even signs Mrita first."""
    i = min(int(deg // 6), 4)
    return BALADI[i if sign % 2 == 0 else 4 - i]  # sign 0 = Aries, an odd sign


def jagradadi(planet: str, sign: int) -> str:
    """Awake in own or exaltation sign, dreaming in a friend's or neutral sign, asleep in an enemy's or fall."""
    d = dignity(planet, sign)
    if d in ("own", "exalted"):
        return "Jagrat (awake)"
    return "Sushupti (asleep)" if d in ("enemy", "debilitated") else "Swapna (dreaming)"


def avasthas(chart: dict) -> dict:
    return {p: {"baladi": baladi(g["sign_index"], g["degrees_in_sign"]), "jagradadi": jagradadi(p, g["sign_index"])}
            for p, g in chart["grahas"].items() if p in P}


# ----- friendship -----
NAT_LABEL = {1: "Friend", 0: "Neutral", -1: "Enemy"}
TAT_LABEL = {1: "Friend", -1: "Enemy"}
PANCH_LABEL = {2: "Great friend", 1: "Friend", 0: "Neutral", -1: "Enemy", -2: "Great enemy"}


def friendship(chart: dict) -> dict:
    signs = {p: chart["grahas"][p]["sign_index"] for p in P}
    nat, tat, five = {}, {}, {}
    for p in P:
        nat[p], tat[p], five[p] = {}, {}, {}
        for q in P:
            if q == p:
                continue
            n = 1 if q in NATURAL[p][0] else 0 if q in NATURAL[p][1] else -1
            t = 1 if (signs[q] - signs[p]) % 12 + 1 in (2, 3, 4, 10, 11, 12) else -1
            nat[p][q], tat[p][q], five[p][q] = NAT_LABEL[n], TAT_LABEL[t], PANCH_LABEL[compound(p, q, signs)]
    return {"natural": nat, "temporary": tat, "fivefold": five}


# ----- Vimshopaka Bala -----
SCHEMES = {
    "shadvarga": {"D1": 6, "D2": 2, "D3": 4, "D9": 5, "D12": 2, "D30": 1},
    "saptavarga": {"D1": 5, "D2": 2, "D3": 3, "D7": 2.5, "D9": 4.5, "D12": 2, "D30": 1},
    "dashavarga": {"D1": 3, "D2": 1.5, "D3": 1.5, "D7": 1.5, "D9": 1.5, "D10": 1.5, "D12": 1.5, "D16": 1.5,
                   "D30": 1.5, "D60": 5},
    "shodashavarga": {"D1": 3.5, "D2": 1, "D3": 1, "D4": 0.5, "D7": 0.5, "D9": 3, "D10": 0.5, "D12": 0.5,
                      "D16": 2, "D20": 0.5, "D24": 0.5, "D27": 0.5, "D30": 1, "D40": 0.5, "D45": 0.5, "D60": 4},
}
# Points out of 20 by the planet's standing in a varga sign (own or exaltation counts in full)
VPTS = {"own": 20, 2: 18, 1: 15, 0: 10, -1: 7, -2: 5}


def vimshopaka(chart: dict) -> dict:
    signs = {p: chart["grahas"][p]["sign_index"] for p in P}
    out = {}
    for p in P:
        row = {}
        for name, weights in SCHEMES.items():
            score = 0.0
            for v, w in weights.items():
                sg = chart["vargas"][v][p]["sign_index"]
                lord = LORD[sg]
                pts = VPTS["own"] if lord == p or dignity(p, sg) == "exalted" or (v == "D1" and sg == MOOLA[p][0]) \
                    else VPTS[compound(p, lord, signs)]
                score += w * pts / 20
            row[name] = round(score, 2)
        out[p] = row
    return out


# ----- upagrahas (Sun-based) -----
def upagrahas(chart: dict) -> list[dict]:
    sun = chart["grahas"]["Sun"]["longitude"]
    dhuma = (sun + 133 + 1 / 3) % 360
    vyati = (360 - dhuma) % 360
    pari = (vyati + 180) % 360
    indra = (360 - pari) % 360
    upaketu = (indra + 16 + 2 / 3) % 360
    lag = chart["lagna"]["sign_index"]
    pts = [("Dhuma", dhuma), ("Vyatipata", vyati), ("Parivesha", pari), ("Indrachapa", indra), ("Upaketu", upaketu)]
    return [{"name": n, "longitude": round(x, 4), "sign": SIGNS[int(x // 30)], "sign_index": int(x // 30),
             "degrees_in_sign": round(x % 30, 4), "house": (int(x // 30) - lag) % 12 + 1} for n, x in pts]


# ----- Sade Sati and dhaiya -----
def _saturn_sign(jd: float, ayan: str) -> int:
    return int(sidereal_longitude(jd, swe.SATURN, ayan)[0] // 30)


@lru_cache(maxsize=8)
def saturn_ingresses(ayan: str, start_year: int, end_year: int) -> tuple:
    """(date, sign) whenever Saturn enters a sign, retrograde re-entries included; found by 5-day steps, then halving."""
    t0 = datetime(start_year, 1, 1, tzinfo=timezone.utc)
    jd, end = julian_day(t0), julian_day(datetime(end_year, 1, 1, tzinfo=timezone.utc))
    out, prev = [], _saturn_sign(jd, ayan)
    out.append((jd, prev))
    while jd < end:
        nxt = jd + 5
        s = _saturn_sign(nxt, ayan)
        if s != prev:
            a, b = jd, nxt
            while b - a > 0.02:
                m = (a + b) / 2
                if _saturn_sign(m, ayan) == prev:
                    a = m
                else:
                    b = m
            out.append((b, s))
            prev = s
        jd = nxt
    return tuple(out)


def _date(jd: float) -> str:
    y, m, d, _ = swe.revjul(jd)
    return f"{y:04d}-{m:02d}-{d:02d}"


def sade_sati(chart: dict, now: datetime | None = None, years: int = 100) -> dict:
    """Sade Sati (Saturn in the 12th, 1st and 2nd from the natal Moon) and the two dhaiyas (4th: Kantaka, 8th:
    Ashtama), each as an episode with its phases; short retrograde exits within an episode are merged."""
    ayan = chart["meta"].get("ayanamsha", "lahiri")
    jd_birth = chart["meta"]["julian_day"]
    by, bm, bd, _ = swe.revjul(jd_birth)
    ing = saturn_ingresses(ayan, int(by) - 3, int(by) + years + 1)
    moon = chart["grahas"]["Moon"]["sign_index"]
    rel = lambda s: (s - moon) % 12 + 1  # house of Saturn's sign counted from the Moon
    spans = []  # (start_jd, end_jd, house from Moon)
    for i, (jd, s) in enumerate(ing):
        end = ing[i + 1][0] if i + 1 < len(ing) else jd + 900
        spans.append((jd, end, rel(s)))

    def episodes(houses: tuple[int, ...]) -> list[dict]:
        eps, cur = [], None
        for a, b, h in spans:
            if h in houses:
                if cur and a - cur["end"] < 400:  # a retrograde dip out and back belongs to the same episode
                    cur["end"] = b
                    cur["phases"].append((a, b, h))
                else:
                    cur = {"start": a, "end": b, "phases": [(a, b, h)]}
                    eps.append(cur)
        return [e for e in eps if e["end"] > jd_birth]

    names = {12: "Rising", 1: "Peak", 2: "Setting", 4: "Kantaka (4th)", 8: "Ashtama (8th)"}

    def fmt(e: dict) -> dict:
        ph = {}
        for a, b, h in e["phases"]:
            if b <= jd_birth:  # a phase that ended before birth is not part of this life
                continue
            k = names[h]
            ph.setdefault(k, [a, b])
            ph[k][0], ph[k][1] = min(ph[k][0], a), max(ph[k][1], b)
        return {"start": _date(max(e["start"], jd_birth)), "end": _date(e["end"]), "from_birth": e["start"] < jd_birth,
                "phases": [{"phase": k, "start": _date(max(v[0], jd_birth)), "end": _date(v[1])} for k, v in ph.items()]}

    ss = [fmt(e) for e in episodes((12, 1, 2))]
    dh = [{**fmt(e), "kind": names[e["phases"][0][2]]} for h in (4, 8) for e in episodes((h,))]
    dh.sort(key=lambda d: d["start"])
    now = now or datetime.now(timezone.utc)
    jn = julian_day(now)
    h_now = next((h for a, b, h in spans if a <= jn < b), None)
    status = {"house_from_moon": h_now, "in_sade_sati": h_now in (12, 1, 2), "phase": names.get(h_now) if h_now in (12, 1, 2) else None,
              "in_dhaiya": names.get(h_now) if h_now in (4, 8) else None,
              "saturn_sign": SIGNS[(moon + h_now - 1) % 12] if h_now else None, "moon_sign": SIGNS[moon]}
    nxt = next((e for e in ss if e["start"] > _date(jn)), None)
    status["next_sade_sati"] = nxt["start"] if nxt else None
    return {"status": status, "episodes": ss, "dhaiyas": dh}


def pro_tables(chart: dict, now: datetime | None = None) -> dict:
    return {"avastha": avasthas(chart), "friendship": friendship(chart), "vimshopaka": vimshopaka(chart),
            "upagrahas": upagrahas(chart), "sade_sati": sade_sati(chart, now)}
