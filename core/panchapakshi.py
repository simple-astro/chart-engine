"""Pancha Pakshi: the Tamil five-bird timing system.

- Birth bird: from the Moon's nakshatra and the paksha at birth (Prof. U.S. Pulippani, "Biorhythms of Natal Moon —
  Mysteries of Pancha Pakshi", ch. 2, tables 1–3).
- Each day (sunrise to sunset) and each night (sunset to next sunrise) is split into five equal yamas. In every yama
  each bird does one main activity — Ruling, Eating, Walking, Sleeping or Dying — and steps one place along that
  half-day's activity cycle each yama. The weekday and paksha (both taken at sunrise, so the night belongs to the day
  before it) fix where the cycle starts.
- Inside a yama the five activities run again as sub-periods, starting with the bird's own main activity and going
  round the same cycle; each sub-period is the main activity of the bird that rules it. Their lengths are fixed
  shares of 144 that differ by paksha and day/night.

The Shukla tables match Pulippani p. 48 as transcribed by VedAstro (MIT); the Krishna tables, the sub-period order and
lengths were read from Drik Panchang (New Delhi, 18 Oct–7 Nov 2026), which also matches every Shukla row checked.
Lahiri nakshatras, the traditional reckoning for this system.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from core import constants as C
from core.panchang import compute_panchang

BIRDS = ["Vulture", "Owl", "Crow", "Cock", "Peacock"]
ACTS = ["Ruling", "Eating", "Walking", "Sleeping", "Dying"]
WEIGHT = {"Ruling": 5, "Eating": 4, "Walking": 3, "Sleeping": 2, "Dying": 1}  # Pulippani's strength order

# (paksha, half) -> activity cycle, the share of 144 each activity's sub-period takes, the order the birds rule the
# sub-periods (consecutive birds hold consecutive activities), and the Vulture's first-yama activity by weekday (Sun..Sat).
_E, _W, _R, _S, _D = "Eating", "Walking", "Ruling", "Sleeping", "Dying"
TABLES = {
    ("Shukla", "day"): {"cycle": [_E, _W, _R, _S, _D], "share": {_E: 30, _W: 36, _R: 48, _S: 18, _D: 12},
                        "order": ["Vulture", "Owl", "Crow", "Cock", "Peacock"],
                        "vulture": [_E, _D, _E, _D, _S, _R, _W]},
    ("Shukla", "night"): {"cycle": [_E, _R, _D, _W, _S], "share": {_E: 30, _R: 24, _D: 36, _W: 30, _S: 24},
                          "order": ["Vulture", "Peacock", "Cock", "Crow", "Owl"],
                          "vulture": [_D, _W, _D, _W, _S, _E, _R]},
    ("Krishna", "day"): {"cycle": [_E, _D, _S, _R, _W], "share": {_E: 48, _D: 30, _S: 12, _R: 18, _W: 36},
                         "order": ["Vulture", "Cock", "Owl", "Peacock", "Crow"],
                         "vulture": [_W, _S, _W, _D, _R, _E, _S]},
    ("Krishna", "night"): {"cycle": [_E, _S, _W, _D, _R], "share": {_E: 42, _S: 18, _W: 42, _D: 24, _R: 18},
                           "order": ["Vulture", "Peacock", "Cock", "Crow", "Owl"],
                           "vulture": [_E, _D, _E, _S, _W, _R, _D]},
}

# Birth bird by Moon nakshatra (0 = Ashwini) and paksha at birth.
_SHUKLA_BIRD = [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [4] * 7
_KRISHNA_BIRD = [4] * 7 + [3] * 5 + [2] * 5 + [1] * 5 + [0] * 5

MEANING = {
    "Ruling": "the bird's strongest time — start, ask, sign, meet",
    "Eating": "a strong time — work, money and requests go well",
    "Walking": "middling — routine work and travel are fine",
    "Sleeping": "weak — rest, wait, don't start anything new",
    "Dying": "the weakest time — avoid new starts and big decisions",
}


def birth_bird(moon_nakshatra: int, paksha: str) -> str:
    return BIRDS[(_SHUKLA_BIRD if paksha == "Shukla" else _KRISHNA_BIRD)[moon_nakshatra]]


def paksha_of(sun_lon: float, moon_lon: float) -> str:
    return "Shukla" if (moon_lon - sun_lon) % 360.0 < 180.0 else "Krishna"


def activity(paksha: str, half: str, weekday: int, yama: int, bird: str) -> str:
    """Main activity of a bird in yama 1..5 of the day or night of a weekday (0 = Sunday)."""
    t = TABLES[(paksha, half)]
    cyc = t["cycle"]
    start = cyc.index(t["vulture"][weekday])
    return cyc[(start + t["order"].index(bird) + yama - 1) % 5]


def rating(main: str, sub: str) -> str:
    good = ("Ruling", "Eating")
    if main in good:
        return "best" if sub in good else "good"
    if main == "Walking":
        return "fair"
    return "avoid"


def _yamas(paksha: str, half: str, weekday: int, start: datetime, end: datetime, bird: str) -> list[dict]:
    t = TABLES[(paksha, half)]
    cyc, step = t["cycle"], (end - start) / 5
    out = []
    for y in range(1, 6):
        y0 = start + step * (y - 1)
        main = activity(paksha, half, weekday, y, bird)
        subs, s0, i0 = [], y0, cyc.index(main)
        for k in range(5):
            act = cyc[(i0 + k) % 5]
            s1 = y0 + step if k == 4 else s0 + step * t["share"][act] / 144
            ruler = t["order"][(t["order"].index(bird) + k) % 5]
            subs.append({"start": s0, "end": s1, "activity": act, "bird": ruler, "rating": rating(main, act),
                         "score": WEIGHT[main] * WEIGHT[act]})
            s0 = s1
        out.append({"half": half, "yama": y, "start": y0, "end": y0 + step, "activity": main, "subs": subs})
    return out


def day_plan(d: date, lat: float, lon: float, tz_name: str, bird: str) -> dict:
    """The bird's ten yamas for the Hindu day that begins at sunrise on d (the night runs to the next sunrise)."""
    p = compute_panchang(d, lat, lon, tz_name)
    nxt = compute_panchang(d + timedelta(days=1), lat, lon, tz_name)
    wd = C.WEEKDAY_NAMES.index(p.weekday)
    yamas = (_yamas(p.paksha, "day", wd, p.sunrise, p.sunset, bird)
             + _yamas(p.paksha, "night", wd, p.sunset, nxt.sunrise, bird))
    return {"date": d.isoformat(), "weekday": p.weekday, "paksha": p.paksha, "bird": bird,
            "sunrise": p.sunrise, "sunset": p.sunset, "next_sunrise": nxt.sunrise, "yamas": yamas}


def best_windows(plan: dict, limit: int = 4) -> list[dict]:
    """The strongest sub-periods of the day and night (main and sub both Ruling or Eating), in clock order."""
    subs = [dict(s, yama=y["yama"], half=y["half"], main=y["activity"]) for y in plan["yamas"] for s in y["subs"]
            if s["rating"] == "best"]
    return sorted(sorted(subs, key=lambda s: (-s["score"], s["start"]))[:limit], key=lambda s: s["start"])


def at(plan: dict, when: datetime) -> dict | None:
    for y in plan["yamas"]:
        if y["start"] <= when < y["end"]:
            sub = next(s for s in y["subs"] if when < s["end"])
            return {"yama": y, "sub": sub}
    return None
