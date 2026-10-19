"""Cheshta Bala (motional strength) and Graha Yuddha (planetary war), for study: not used in readings.

Brihat Parashara Hora Shastra, chapter 27:
- vv. 21-23 name eight motions and their strength out of 60: Vakra (retrograde) 60, Anuvakra 30, Vikala 15, Madhya
  or Sama 30, Manda 15, Mandatara 30, Chara 45, Ati-chara 30. The verses give no speed limits for each motion, so
  the label here comes from the planet's speed against its average speed, with cut-offs of our own (MOTION).
- v. 24 gives the calculation used for the value: Cheshta Kendra = seeghrochcha - (mean + true longitude) / 2,
  reduced to 0-180 degrees; Cheshta Bala = Cheshta Kendra / 3 (out of 60). For Mars, Jupiter and Saturn the
  seeghrochcha is the mean Sun and the mean longitude the planet's own; for Mercury and Venus the seeghrochcha is the
  planet's own mean (heliocentric) longitude and the mean longitude the mean Sun. Mean longitudes are Meeus's.
- The Sun's Cheshta Bala is taken as its Ayana Bala ((24 + declination) / 48 x 60) and the Moon's as its Paksha Bala
  (distance from the Sun, reduced to 0-180, / 3), as most Shadbala texts and programs do.
Graha Yuddha: two of Mars, Mercury, Jupiter, Venus and Saturn within 1 degree of longitude. Texts differ on the
winner (northern latitude, brightness, size); this names the planet further north, the most common rule.
"""
from __future__ import annotations

import swisseph as swe

# (L at J2000, degrees per Julian century): mean longitudes of date (Meeus, Astronomical Algorithms, table 31.A)
MEAN = {"Sun": (280.46646, 36000.76983), "Mercury": (252.250906, 149474.0722491), "Venus": (181.979801, 58519.2130302),
        "Mars": (355.433, 19141.6964471), "Jupiter": (34.351519, 3036.3027748), "Saturn": (50.077444, 1223.5110686)}
AVG_SPEED = {"Mercury": 0.9856, "Venus": 0.9856, "Mars": 0.5240, "Jupiter": 0.0831, "Saturn": 0.0335}
SUPERIOR = {"Mars", "Jupiter", "Saturn"}
# Speed against the average -> the BPHS motion name and its verse value (label only; the value shown uses v. 24).
MOTION = [(0.1, "Vikala", "nearly standing still", 15), (0.5, "Mandatara", "slower", 30), (0.9, "Manda", "slow", 15),
          (1.1, "Sama", "average", 30), (1.5, "Chara", "fast", 45), (99.0, "Ati-chara", "very fast", 30)]
WAR = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def _mean(body: str, jd: float) -> float:
    l0, n = MEAN[body]
    return (l0 + n * (jd - 2451545.0) / 36525.0) % 360


def _true(jd: float, pid: int) -> tuple[float, float, float]:
    """Tropical geocentric longitude, latitude and speed."""
    x, _ = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
    return x[0], x[1], x[3]


def _fold(k: float) -> float:
    k %= 360
    return 360 - k if k > 180 else k


def motion(planet: str, speed: float) -> dict:
    if speed < 0:
        return {"name": "Vakra", "plain": "retrograde", "verse_value": 60}
    r = speed / AVG_SPEED[planet]
    name, plain, val = next((n, p, v) for lim, n, p, v in MOTION if r < lim)
    return {"name": name, "plain": plain, "verse_value": val, "ratio": round(r, 2)}


def cheshta(jd: float) -> dict:
    """Cheshta Bala of the seven planets (0-60), the motion of the five star planets, and any planetary war."""
    sun_mean = _mean("Sun", jd)
    out, pos = {}, {}
    for p, pid in (("Mars", swe.MARS), ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
                   ("Saturn", swe.SATURN)):
        lon, lat, spd = _true(jd, pid)
        pos[p] = (lon, lat)
        seeghra, mean = (sun_mean, _mean(p, jd)) if p in SUPERIOR else (_mean(p, jd), sun_mean)
        k = _fold(seeghra - (mean + lon) / 2)
        out[p] = {"value": round(k / 3, 1), "kendra": round(k, 1), "speed": round(spd, 4), **motion(p, spd)}
    x, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)
    dec = x[1]
    out["Sun"] = {"value": round(max(0.0, min(60.0, (24 + dec) / 48 * 60)), 1), "name": "Ayana Bala",
                  "plain": f"{abs(dec):.1f}° {'north' if dec >= 0 else 'south'} of the equator", "declination": round(dec, 2)}
    sun_lon = _true(jd, swe.SUN)[0]
    moon_lon = _true(jd, swe.MOON)[0]
    elong = (moon_lon - sun_lon) % 360
    out["Moon"] = {"value": round(_fold(elong) / 3, 1), "name": "Paksha Bala",
                   "plain": f"{'waxing' if elong < 180 else 'waning'}, {round(_fold(elong))}° from the Sun"}
    wars = []
    for i, a in enumerate(WAR):
        for b in WAR[i + 1:]:
            gap = abs((pos[a][0] - pos[b][0] + 180) % 360 - 180)
            if gap < 1:
                win, lose = (a, b) if pos[a][1] > pos[b][1] else (b, a)
                wars.append({"planets": [a, b], "gap": round(gap, 2), "winner": win, "loser": lose,
                             "rule": "the planet further north (higher ecliptic latitude) wins; texts differ"})
    closest = min(((abs((pos[a][0] - pos[b][0] + 180) % 360 - 180), a, b) for i, a in enumerate(WAR) for b in WAR[i + 1:]))
    return {"planets": out, "wars": wars, "closest": {"planets": [closest[1], closest[2]], "gap": round(closest[0], 1)}}
