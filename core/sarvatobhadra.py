"""Sarvatobhadra Chakra: the 9×9 grid of 28 nakshatras (with Abhijit), 16 vowels, 20 consonants, 12 signs and the five
tithi groups with their weekdays, and the vedha (strike) each planet casts across it.

- Layout as in PyJHora (AGPL-3.0, jhora/ui/chakra.py), drawn with north at the top and east on the right: Krittika
  starts the east side, the corner vowels a, ā, i, ī sit between the sides, and the inner rings hold the consonants,
  the signs and the tithi groups.
- Vedha: a planet strikes along three lines from its nakshatra — straight across the grid (front) and the two
  diagonals — and everything those lines cross is struck, plus the nakshatra it stands in. The classical texts
  (Phaladeepika, Ojha's commentary) give each planet one main line by its motion; like Jagannatha Hora this module
  draws all three for every planet and reports retrograde motion, which makes the strike stronger.
- A planet in the last pada before a corner or the first pada after it also strikes that corner's vowel.
- Benefic strikes: the waxing Moon, Mercury, Jupiter, Venus. Malefic: the waning Moon, Sun, Mars, Saturn, Rahu, Ketu.
- Money days: the slow planets set the background on the birth chakra's money points for weeks at a time; the
  Moon, which crosses a nakshatra a day, is what turns a single day good or difficult.
- Abhijit runs from 276°40′ to 280°53′20″ (the last pada of Uttarashadha and the first 1/15 of Shravana).
- Markets (teji-mandi): a malefic strike on a nakshatra is read as prices rising (teji) for the goods it rules, a
  benefic strike as prices falling (mandi). Which goods each nakshatra rules is the astrologer's table, kept as data.
Lahiri ayanamsha, mean node, the traditional reckoning for this chakra.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core import constants as C
from core.ephemeris import julian_day
from core.grahas import compute_grahas

AYAN = "lahiri"
ABHIJIT = 27
NAK28 = C.NAKSHATRAS + ["Abhijit"]
BENEFIC = {"Moon", "Mercury", "Jupiter", "Venus"}
MALEFIC = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
GROUPS = ["Nanda", "Bhadra", "Jaya", "Rikta", "Purna"]
GROUP_DAYS = {"Nanda": ["Sunday", "Tuesday"], "Bhadra": ["Monday", "Wednesday"], "Jaya": ["Thursday"],
              "Rikta": ["Friday"], "Purna": ["Saturday"]}

# ("n", k): nakshatra k (0 = Ashwini, 27 = Abhijit); ("s", k): sign k; ("v", text) vowel; ("c", text) consonant;
# ("t", group) tithi group with its weekdays.
_n = lambda k: ("n", k)
_s = lambda k: ("s", k)
_v = lambda t: ("v", t)
_c = lambda t: ("c", t)
_t = lambda g: ("t", g)
GRID = [
    [_v("ई ī"), _n(22), _n(23), _n(24), _n(25), _n(26), _n(0), _n(1), _v("अ a")],
    [_n(21), _v("ॠ ṝ"), _c("ग ga"), _c("स sa"), _c("द da"), _c("च cha"), _c("ल la"), _v("उ u"), _n(2)],
    [_n(ABHIJIT), _c("ख kha"), _v("ऐ ai"), _s(10), _s(11), _s(0), _v("ऌ ḷ"), _c("अ a"), _n(3)],
    [_n(20), _c("ज ja"), _s(9), _v("अः aḥ"), _t("Rikta"), _v("ओ o"), _s(1), _c("व va"), _n(4)],
    [_n(19), _c("भ bha"), _s(8), _t("Jaya"), _t("Purna"), _t("Nanda"), _s(2), _c("क ka"), _n(5)],
    [_n(18), _c("य ya"), _s(7), _v("अं aṃ"), _t("Bhadra"), _v("औ au"), _s(3), _c("ह ha"), _n(6)],
    [_n(17), _c("न na"), _v("ए e"), _s(6), _s(5), _s(4), _v("ॡ ḹ"), _c("ड ḍa"), _n(7)],
    [_n(16), _v("ऋ ṛ"), _c("त ta"), _c("र ra"), _c("प pa"), _c("ट ṭa"), _c("म ma"), _v("ऊ ū"), _n(8)],
    [_v("इ i"), _n(15), _n(14), _n(13), _n(12), _n(11), _n(10), _n(9), _v("आ ā")],
]
WHERE = {cell: (r, c) for r, row in enumerate(GRID) for c, cell in enumerate(row)}
# Corner vowel struck by the last pada before it and the first pada after it (nakshatra, pada).
CORNERS = {(0, 8): ((1, 4), (2, 1)), (8, 8): ((8, 4), (9, 1)), (8, 0): ((15, 4), (16, 1)), (0, 0): ((21, 4), (22, 1))}

_ABHIJIT_START, _ABHIJIT_END = 276 + 40 / 60, 280 + 53 / 60 + 20 / 3600


def nak28(lon: float) -> int:
    lon %= 360.0
    return ABHIJIT if _ABHIJIT_START <= lon < _ABHIJIT_END else int(lon // C.NAKSHATRA_ARC)


def label(cell: tuple) -> str:
    kind, v = cell
    if kind == "n":
        return NAK28[v]
    if kind == "s":
        return C.SIGNS[v]
    if kind == "t":
        return f"{v} ({', '.join(GROUP_DAYS[v])})"
    return v


def _walk(r: int, c: int, dr: int, dc: int) -> list[tuple[int, int]]:
    out = []
    r, c = r + dr, c + dc
    while 0 <= r < 9 and 0 <= c < 9:
        out.append((r, c))
        r, c = r + dr, c + dc
    return out


def lines(nak: int) -> dict[str, list[tuple[int, int]]]:
    """The cells struck from a nakshatra: straight across (front) and along the two inward diagonals."""
    r, c = WHERE[_n(nak)]
    if r == 0:
        inward, side = (1, 0), (0, 1)
    elif r == 8:
        inward, side = (-1, 0), (0, 1)
    elif c == 0:
        inward, side = (0, 1), (1, 0)
    else:
        inward, side = (0, -1), (1, 0)
    diag = lambda s: _walk(r, c, inward[0] + s * side[0], inward[1] + s * side[1])
    return {"front": _walk(r, c, *inward), "diagonal_1": diag(1), "diagonal_-1": diag(-1)}


def nature(name: str, grahas: dict) -> str:
    if name == "Moon" and "Sun" in grahas:
        return "benefic" if (grahas["Moon"][0] - grahas["Sun"][0]) % 360 < 180 else "malefic"
    return "benefic" if name in BENEFIC else "malefic"


def strikes(grahas: dict) -> dict[tuple[int, int], list[dict]]:
    """Every struck cell -> [{planet, nature, line, retrograde}] for the planets in `grahas` (name -> longitude, retro).
    A planet is listed once per cell, by the strongest way it reaches it (in > front > diagonal > corner)."""
    hit: dict[tuple[int, int], list[dict]] = {}
    for name, (lon, retro) in grahas.items():
        k = nak28(lon)
        base = {"planet": name, "nature": nature(name, grahas), "retrograde": retro}
        seen: set = set()

        def add(rc, line):
            if rc not in seen:
                seen.add(rc)
                hit.setdefault(rc, []).append({**base, "line": line})
        add(WHERE[_n(k)], "in")
        ln = lines(k)
        for rc in ln["front"]:
            add(rc, "front")
        for rc in ln["diagonal_1"] + ln["diagonal_-1"]:
            add(rc, "diagonal")
        nak, pada = int(lon % 360 // C.NAKSHATRA_ARC), int(lon % C.NAKSHATRA_ARC // C.PADA_ARC) + 1
        for corner, ends in CORNERS.items():
            if (nak, pada) in ends:
                add(corner, "corner")
    return hit


def sky(when: datetime) -> dict[str, tuple[float, bool]]:
    g = compute_grahas(julian_day(when), AYAN)
    return {n: (x.longitude, x.retrograde) for n, x in g.items()}


def grid_view(grahas: dict, marks: dict[tuple[int, int], list[str]] | None = None) -> list[list[dict]]:
    """The 81 cells, each with its label, the planets standing in it and the strikes on it."""
    hit = strikes(grahas)
    stand: dict[tuple[int, int], list[str]] = {}
    for name, (lon, retro) in grahas.items():
        stand.setdefault(WHERE[_n(nak28(lon))], []).append(name + ("(R)" if retro else ""))
    return [[{"kind": GRID[r][c][0], "label": label(GRID[r][c]), "planets": stand.get((r, c), []),
              "strikes": hit.get((r, c), []), "marks": (marks or {}).get((r, c), [])}
             for c in range(9)] for r in range(9)]


def tithi_group(sun_lon: float, moon_lon: float) -> str:
    t = int((moon_lon - sun_lon) % 360 // 12) % 15 + 1  # 1..15 within the paksha (Purnima and Amavasya are 15)
    return GROUPS[(t - 1) % 5]


def natal_points(moon_lon: float, sun_lon: float, lagna_sign: int, weekday: str) -> dict[str, tuple[int, int]]:
    """The birth points read on the chakra; the 2nd and 11th signs from the lagna carry money and gains."""
    group = tithi_group(sun_lon, moon_lon)
    pts = {"Birth nakshatra": WHERE[_n(nak28(moon_lon))], "Moon sign": WHERE[_s(int(moon_lon // 30))],
           "Lagna": WHERE[_s(lagna_sign)], "2nd house (wealth)": WHERE[_s((lagna_sign + 1) % 12)],
           "11th house (gains)": WHERE[_s((lagna_sign + 10) % 12)],
           f"Birth tithi ({group})": WHERE[_t(group)]}
    weekday_group = next(g for g, days in GROUP_DAYS.items() if weekday in days)
    pts[f"Birth weekday ({weekday})"] = WHERE[_t(weekday_group)]
    return pts


MONEY_WEIGHT = {"Birth nakshatra": 2, "2nd house (wealth)": 2, "11th house (gains)": 2, "Moon sign": 1, "Lagna": 1}


def money_day(points: dict[str, tuple[int, int]], grahas: dict) -> dict:
    """The day's reading on the money points. Points sharing a box (Moon sign = lagna) count once, at the higher weight.
    Good: the Moon supports a money point and the day's total is clearly positive. Careful: the Moon presses on one
    and the total is negative, or the background alone is heavily negative."""
    hit = strikes(grahas)
    cells: dict[tuple[int, int], tuple[int, str]] = {}
    for name, rc in points.items():
        w = MONEY_WEIGHT.get(name)
        if w and (rc not in cells or w > cells[rc][0]):
            cells[rc] = (w, " and ".join(n for n, x in points.items() if x == rc and n in MONEY_WEIGHT))
    moon = backdrop = 0
    why = []
    for rc, (w, name) in cells.items():
        for s in hit.get(rc, []):
            v = w if s["nature"] == "benefic" else -w
            if s["planet"] == "Moon":
                moon += v
            else:
                backdrop += v
            why.append({"point": name, **s})
    score = moon + backdrop
    verdict = ("good" if moon > 0 and score >= 3 else
               "careful" if (moon < 0 and score <= -1) or score <= -5 else "mixed")
    why.sort(key=lambda x: (x["planet"] != "Moon", x["nature"] != "benefic"))
    return {"score": score, "moon": moon, "backdrop": backdrop, "verdict": verdict, "why": why}


def money_days(points: dict, start: date, days: int, tz_name: str) -> list[dict]:
    tz = ZoneInfo(tz_name)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({"date": d.isoformat(), **money_day(points, sky(datetime.combine(d, time(12), tzinfo=tz)))})
    return out


def market(when: datetime, goods: dict[int, str] | None = None) -> list[dict]:
    """Each nakshatra's strikes and its teji (rise) / mandi (fall) reading, with the goods the astrologer linked to it."""
    hit = strikes(sky(when))
    rows = []
    for k in range(28):
        s = hit.get(WHERE[_n(k)], [])
        mal = sorted({x["planet"] for x in s if x["nature"] == "malefic"})
        ben = sorted({x["planet"] for x in s if x["nature"] == "benefic"})
        signal = "teji" if mal and not ben else "mandi" if ben and not mal else "mixed" if s else "quiet"
        rows.append({"nakshatra": NAK28[k], "index": k, "malefic": mal, "benefic": ben, "signal": signal,
                     "goods": (goods or {}).get(k, "")})
    return rows
