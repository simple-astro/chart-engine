"""Transits for a date laid over the natal chart, with the running daśā and how the two line up."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

from app.muhurat import TARAS
from core.ashtakavarga import ashtakavarga
from core.constants import SIGNS
from core.kp import kp_lords, planet_house
from core.kp_predict import own_houses
from core.transits import transit_positions

ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
THEME = {1: "self and health", 2: "money and family", 3: "effort and siblings", 4: "home and mother",
         5: "children and studies", 6: "work and health issues", 7: "marriage and partners", 8: "sudden changes",
         9: "luck and father", 10: "career", 11: "gains and income", 12: "expenses and travel abroad"}
LEVEL = {"maha": "Mahadasha", "antar": "Antardasha", "praty": "Pratyantar"}


def _h(sign: int, base: int) -> int:
    return (sign - base) % 12 + 1


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _sep(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def dasha_on(chart: dict, when: datetime) -> list[dict]:
    """[maha, antar, pratyantar] running at ``when``."""
    iso = when.isoformat()
    out, level = [], chart["dasha"]
    for name in ("maha", "antar", "praty"):
        node = next((d for d in level if d["start"] <= iso < d["end"]), None)
        if not node:
            break
        out.append({"level": name, "lord": node["lord"], "start": node["start"][:10], "end": node["end"][:10]})
        level = node.get("children") or []
    return out


def overlay(profile: dict, day: date, hour: int = 12) -> dict:
    chart, req = profile["chart"], profile.get("request") or {}
    tz = ZoneInfo(req.get("tz_name") or "UTC")
    when = datetime(day.year, day.month, day.day, hour, tzinfo=tz)
    tr = transit_positions(when.astimezone(timezone.utc), chart["meta"].get("ayanamsha", "krishnamurti"),
                           node_type=chart["meta"].get("node_type", "mean"))
    L = chart["lagna"]["sign_index"]
    natal = chart["grahas"]
    moon_sign = natal["Moon"]["sign_index"]
    cusps = NS(cusps=[NS(house=c["house"], longitude=c["longitude"]) for c in chart["houses"]])
    sav = ashtakavarga({p: g["sign_index"] for p, g in natal.items()}, L)["sav"]
    dba = dasha_on(chart, when)
    levels: dict[str, list[str]] = {}
    for d in dba:
        levels.setdefault(d["lord"], []).append(LEVEL[d["level"]])
    role = lambda p: " and ".join(levels[p])  # e.g. "Antardasha and Pratyantar"
    dlords = set(levels)

    rows = []
    for p in ORDER:
        g = tr[p]
        k = kp_lords(g.longitude)
        over = [q for q in ORDER if _sep(g.longitude, natal[q]["longitude"]) <= 3.0]
        rows.append({
            "planet": p, "sign": g.sign, "sign_index": g.sign_index, "deg": round(g.degrees_in_sign, 2),
            "nakshatra": g.nakshatra, "pada": g.pada, "star_lord": k.star_lord, "sub_lord": k.sub_lord,
            "retrograde": bool(g.retrograde) and p not in ("Rahu", "Ketu"), "speed": round(g.speed, 4),
            "h_lagna": _h(g.sign_index, L), "h_moon": _h(g.sign_index, moon_sign),
            "h_bhava": planet_house(g.longitude, cusps), "sav": sav[g.sign_index],
            "over_natal": over, "dasha": role(p) if p in levels else "",
        })
    by = {r["planet"]: r for r in rows}

    notes = []
    sm = by["Saturn"]["h_moon"]
    if sm in (12, 1, 2):
        notes.append({"kind": "care", "text": f"Sade Sati — {'rising' if sm == 12 else 'peak' if sm == 1 else 'setting'} phase: "
                      "Saturn is passing over your Moon sign area. Steady effort, patience and Saturday upay help."})
    elif sm == 8:
        notes.append({"kind": "care", "text": "Ashtama Shani — Saturn 8th from your Moon: go carefully with health and big risks."})
    elif sm == 4:
        notes.append({"kind": "care", "text": "Kantaka Shani — Saturn 4th from your Moon: home and peace of mind need care."})
    jm = by["Jupiter"]["h_moon"]
    notes.append({"kind": "good" if jm in (2, 5, 7, 9, 11) else "neutral",
                  "text": f"Jupiter is {_ord(jm)} from your Moon — " + ("a supportive position for growth and good news."
                          if jm in (2, 5, 7, 9, 11) else "not one of its best positions from the Moon; growth comes slower.")})
    for p in levels:
        r = by[p]
        sig = own_houses(chart, p)
        hit = r["h_bhava"] in sig
        notes.append({"kind": "good" if hit else "neutral",
                      "text": f"{role(p)} lord {p} is transiting your {_ord(r['h_bhava'])} house "
                              f"({THEME[r['h_bhava']]})" + (f" — a house it rules or occupies in your birth chart, so its "
                              f"period's results are more active now." if hit else ".")})
    for r in rows:
        if r["star_lord"] in dlords and r["planet"] not in dlords and r["planet"] in ("Sun", "Mars", "Jupiter", "Saturn"):
            notes.append({"kind": "good", "text": f"{r['planet']} moves through the star of {r['star_lord']}, your "
                          f"{role(r['star_lord'])} lord — it carries that period's themes while it stays in this star."})
        for q in r["over_natal"]:
            if r["planet"] != "Moon" and (r["planet"] in dlords or q in dlords):
                notes.append({"kind": "neutral", "text": f"Transit {r['planet']} is over your natal {q} "
                              f"(within 3°) — a sensitive point while {', '.join(sorted({r['planet'], q} & set(dlords)))} "
                              "runs a daśā period."})
    birth_nak = natal["Moon"]["nakshatra_index"]
    t_name, t_score, t_note = TARAS[(tr["Moon"].nakshatra_index - birth_nak) % 27 % 9]
    moon_today = {"nakshatra": tr["Moon"].nakshatra, "sign": tr["Moon"].sign, "tara": t_name, "tara_note": t_note,
                  "tara_score": t_score, "h_moon": by["Moon"]["h_moon"]}
    return {"date": day.isoformat(), "time": f"{hour:02d}:00", "tz": str(tz), "lagna_sign": SIGNS[L],
            "lagna_index": L, "moon_sign": SIGNS[moon_sign], "dasha": dba, "planets": rows, "notes": notes,
            "moon_today": moon_today}
