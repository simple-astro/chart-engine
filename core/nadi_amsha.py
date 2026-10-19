"""D150, the Nadi amsha: each sign split into 150 parts of 0°12′, numbered the Chandra Kala Nadi way.

- Movable signs (Aries, Cancer, Libra, Capricorn): counted forward from the start of the sign.
- Fixed signs (Taurus, Leo, Scorpio, Aquarius): counted backward from the end of the sign.
- Dual signs (Gemini, Virgo, Sagittarius, Pisces): counted from the middle (15°) forward to the end, then on from
  the start, so the part at 15°00′ is no. 1 and the part at 0°00′ is no. 76.
- The D150 chart: the n-th Nadi amsha falls in the n-th sign counted from the sign itself (as D60 counts).
A part lasts about 48 seconds of birth time for the Lagna (faster or slower with the rising sign), which is why Nadi
readers use it to confirm the birth time and to tell twins apart. ``lagna_window`` says how many seconds earlier or
later the birth would move the Lagna into the next part.
"""
from __future__ import annotations

from core import constants as C
from core.houses import compute_houses

PART = 30 / 150  # 0°12′


def number(longitude: float) -> int:
    """The Chandra Kala Nadi number (1-150) of the part ``longitude`` falls in."""
    s, d = int(longitude % 360 // 30), longitude % 30
    i = min(149, int(d / PART + 1e-9))       # 0-based part from the start of the sign
    kind = s % 3                              # 0 movable, 1 fixed, 2 dual
    if kind == 0:
        return i + 1
    if kind == 1:
        return 150 - i
    return (i - 75) % 150 + 1


def d150_sign(longitude: float) -> int:
    s = int(longitude % 360 // 30)
    return (s + number(longitude) - 1) % 12


def point(longitude: float) -> dict:
    s, d = int(longitude % 360 // 30), longitude % 30
    i = min(149, int(d / PART + 1e-9))
    return {"sign": C.SIGNS[s], "deg": round(d, 4), "number": number(longitude),
            "from": round(i * PART, 4), "to": round((i + 1) * PART, 4), "d150_sign": C.SIGNS[d150_sign(longitude)]}


def lagna_window(jd: float, lat: float, lon: float, ayanamsha: str) -> dict:
    """Seconds of birth time to the edges of the Lagna's Nadi amsha (earlier and later)."""
    asc = lambda t: compute_houses(t, lat, lon, ayanamsha).ascendant
    part = lambda t: int(asc(t) // PART)
    here = part(jd)

    def edge(sign: int) -> int:
        step = sign / 86400                   # one second, in days
        lo, hi = 0, 1
        while part(jd + hi * step) == here and hi < 1200:
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if part(jd + mid * step) == here:
                lo = mid
            else:
                hi = mid
        return hi

    return {"earlier": edge(-1), "later": edge(1)}


def analyse(chart: dict, lat: float, lon: float) -> dict:
    pts = {"Lagna": point(chart["lagna"]["ascendant"])}
    pts.update({n: point(g["longitude"]) for n, g in chart["grahas"].items()})
    win = lagna_window(chart["meta"]["julian_day"], lat, lon, chart["meta"]["ayanamsha"])
    return {"points": pts, "lagna_window": win, "counting": "Chandra Kala Nadi"}
