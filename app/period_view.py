"""What the running period lords promise, across every life matter, and what their transits are doing now.

Each running dasha lord (Maha, Antar, Pratyantar) is judged for every matter at planet / star lord / sub lord
level (core.kp_predict.lord_verdict — the same judgement the timing engine uses, natural significators included).
The matter's window verdict combines them Dasa -> Bhukti -> Antar. Where that same planet is transiting on the day
is read the Nadi way too (its transit star and sub lords through the natal houses), shown as a hint only: transit
triggers did not pin down dated events in our backtest (scripts/backtest_transit_trigger.py).
"""
from __future__ import annotations

from datetime import date

from app.transit_events import transit_verdict
from core import kp_predict as K

TOPICS = ["marriage", "love", "career", "business", "job_change", "money", "property", "vehicle", "foreign",
          "children", "education", "health", "illness"]
SHORT = {"marriage": "Marriage", "love": "Relationship", "career": "Job & promotion", "business": "Business",
         "job_change": "Job change", "money": "Money", "property": "Property", "vehicle": "Vehicle",
         "foreign": "Abroad", "children": "Children", "education": "Education", "health": "Good health",
         "illness": "Health care"}
LEVEL = {"maha": "Mahadasha", "antar": "Antardasha", "praty": "Pratyantar"}
GOOD = ("supports", "leans good")
BAD = ("against", "blocks")


def _join(xs: list[str]) -> str:
    xs = [x.lower() for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _lord_summary(title: str, lord: str, strong: list[str], leans: list[str], against: list[str], care: bool) -> str:
    v = "" if " and " in title else "s"  # "Antardasha and Pratyantar support"
    bits = []
    if strong:
        bits.append(f"strongly support{v} {_join(strong)}")
    if leans:
        bits.append(f"lean{v} towards {_join(leans)}")
    if against:
        bits.append(f"work{v} against {_join(against)}")
    if care == "mixed":
        bits.append(f"give{v} mixed signals for health — keep a steady routine")
    elif care:
        bits.append(f"ask{v} for care with health")
    return f"Your {lord} {title} " + ("; ".join(bits) if bits else f"{'is' if v else 'are'} neutral for most matters") + "."


def periods(chart: dict, day: date, dasha: list[dict], planets: list[dict]) -> dict:
    lords = [(d["level"], d["lord"], d) for d in dasha]
    tr = {r["planet"]: r for r in planets}
    hs = lambda p: set(K.own_houses(chart, p))
    cells = {t: {lv: K.lord_verdict(chart, t, lord) for lv, lord, _ in lords} for t in TOPICS}

    out_lords = []
    seen: dict[str, dict] = {}
    for lv, lord, d in lords:
        if lord in seen:  # the same planet running two levels is read once ("Antardasha and Pratyantar")
            seen[lord]["title"] += f" and {LEVEL[lv]}"
            seen[lord]["levels_run"].append(lv)
            continue
        g = chart["grahas"][lord]
        j = cells[TOPICS[0]][lv]  # any topic: the levels' lords are the same
        ev = [t for t in TOPICS if K.TOPICS[t][6] == "event"]
        strong = [SHORT[t] for t in ev if cells[t][lv]["verdict"] == "supports"]
        leans = [SHORT[t] for t in ev if cells[t][lv]["verdict"] == "leans good"]
        against = [SHORT[t] for t in TOPICS if K.TOPICS[t][6] == "event" and cells[t][lv]["verdict"] in BAD]
        care = cells["illness"][lv]["verdict"] in GOOD
        if care and SHORT["health"] in strong + leans:  # 1/5/11 and 6/8/12 both signified: say mixed, not both
            strong, leans = [x for x in strong if x != SHORT["health"]], [x for x in leans if x != SHORT["health"]]
            care = "mixed"
        t = tr.get(lord)
        transit = None
        if t and t["retrograde"]:  # Taneja: a retrograde transiting planet carries no meaning until it is direct
            transit = {"house": t["h_bhava"], "sign": t["sign"], "star_lord": t["star_lord"], "sub_lord": t["sub_lord"],
                       "retrograde": True, "supports": [], "promised_too": []}
        elif t:
            h_star, h_sub = hs(t["star_lord"]), hs(t["sub_lord"])
            tv = {x: transit_verdict(h_star, h_sub, K.TOPICS[x][2], K.TOPICS[x][3]) for x in TOPICS}
            transit = {"house": t["h_bhava"], "sign": t["sign"], "star_lord": t["star_lord"], "sub_lord": t["sub_lord"],
                       "retrograde": t["retrograde"],
                       "supports": [SHORT[x] for x in TOPICS if K.TOPICS[x][6] == "event" and tv[x] == "supports"],
                       "promised_too": [SHORT[x] for x in TOPICS if K.TOPICS[x][6] == "event" and tv[x] == "supports"
                                        and cells[x][lv]["verdict"] in GOOD]}
        promises = strong + leans
        seen[lord] = {
            "level": lv, "levels_run": [lv], "title": LEVEL[lv], "lord": lord, "start": d["start"], "end": d["end"],
            "natal": {"house": g["house"], "sign": g["sign"], "star_lord": j["star_lord"], "sub_lord": j["sub_lord"],
                      "levels": {k: v["houses"] for k, v in j["levels"].items()}, "retrograde": g["retrograde"]},
            "promises": promises, "strong": strong, "leans": leans, "against": against, "care": care,
            "transit": transit}
        out_lords.append(seen[lord])
    for x in out_lords:
        x["summary"] = _lord_summary(x["title"], x["lord"], x["strong"], x["leans"], x["against"], x["care"])

    matrix = []
    for t in TOPICS:
        title, cusp, good, bad, _, _, kind = K.TOPICS[t]
        win = K.predict(chart, t, start=day, months=1)["windows"]
        matrix.append({"topic": t, "title": SHORT[t], "kind": kind, "houses_for": sorted(good),
                       "houses_against": sorted(bad), "promise": K.promise(chart, t)["verdict"],
                       "cells": {lv: {"verdict": c["verdict"], "note": c.get("note"),
                                      "levels": {k: v["houses"] for k, v in c["levels"].items()}}
                                 for lv, c in cells[t].items()},
                       "window": win[0]["verdict"] if win else None})
    return {"lords": out_lords, "matrix": matrix}
