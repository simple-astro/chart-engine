"""Backtest Nadi / KP nuances one at a time against the book's dated events.

For each variant the engine is patched, then for the book's 17 events we count how many fall in windows rated
favourable-or-better and strong, and compare with the base rate: the share of time within +-10 years of each
event that the same chart is rated that well for the same topic. Lift = hit rate / base rate. A nuance earns its
place only if it raises lift without losing events.

Run: .venv/bin/python scripts/backtest_nuances.py
"""
import sys
from contextlib import contextmanager
from datetime import date, timedelta

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core import kp_predict as K  # noqa: E402
from test_book_backtest import EVENTS, verdict_at_book_dba  # noqa: E402

GOOD = ("strong", "favourable")
_judge, _own, _predict = K.judge_lord, K.own_houses, K.predict


# ---------- variant 1: Taneja's named strength categories ----------
def _state(h: set, good: set, bad: set, fac: set) -> str:
    f, a = h & good, h & bad
    return "both" if f and a else "for" if f else "against" if a else "fac" if h & fac else "none"


def judge_taneja(chart, p, good, bad, risk=None, fac=None):
    j = _judge(chart, p, good, bad, risk, fac)
    if risk is not None:
        return j
    st = {lvl: _state(set(v["houses"]), good, bad, fac or set()) for lvl, v in j["levels"].items()}
    sub, star, pl = st["sub"], st["nakshatra"], st["planet"]
    if sub == "against":                       # weak: the sub lord negates -> it won't happen
        v = "blocks" if star == "against" else "against"
    elif sub == "for":                         # strongest when the star agrees; average (with difficulty) otherwise
        v = "supports" if star == "for" else "leans good"
    elif sub == "fac" and star == "for" and pl == "for":   # full strength
        v = "supports"
    elif sub == "both":
        v = "leans good" if star == "for" else "mixed"
    else:                                      # ordinary: depends on the other dasha lords
        v = "against" if star == "against" and pl == "against" else "mixed"
    return {**j, "verdict": v}


# ---------- variant 2: cusp sub lord in the star of a retrograde planet ----------
def predict_retro_csl(chart, topic, start=None, months=24):
    out = _predict(chart, topic, start, months)
    csl = chart["houses"][K.TOPICS[topic][1] - 1]["kp"]["sub_lord"]
    star = chart["grahas"][csl]["nakshatra_lord"]
    if chart["grahas"][star]["retrograde"] and star not in ("Rahu", "Ketu"):
        for w in out["windows"]:  # the matter does not come in the cusp sub lord's own periods
            if csl in (w["antar"], w["praty"]) and w["verdict"] in GOOD:
                w["verdict"] = "mixed"
    return out


# ---------- variant 3: a DBA lord in the star of a retrograde planet is delayed (one step down) ----------
def judge_retro_star(chart, p, good, bad, risk=None, fac=None):
    j = _judge(chart, p, good, bad, risk, fac)
    star = chart["grahas"][p]["nakshatra_lord"]
    if risk is None and chart["grahas"][star]["retrograde"] and star not in ("Rahu", "Ketu"):
        steps = ["blocks", "against", "mixed", "leans good", "supports"]
        j = {**j, "verdict": steps[max(0, steps.index(j["verdict"]) - 1)]}
    return j


# ---------- variant 4: planets conjunct within 3°20' act as agents of each other ----------
def own_conjunct(chart, p):
    h = set(_own(chart, p))
    if p in ("Rahu", "Ketu"):
        return h
    lon = {q: g["longitude"] for q, g in chart["grahas"].items() if q not in ("Rahu", "Ketu")}
    for q in lon:
        d = abs(lon[q] - lon[p]) % 360
        if q != p and min(d, 360 - d) <= 10 / 3:
            s = chart["significators"]["by_planet"][q]
            h |= set(s["occupied"]) | set(s["owned"])
    return h


# ---------- variant 5: self-strength (4-step) — secondary significations dropped ----------
def own_self_strength(chart, p):
    if p in ("Rahu", "Ketu"):
        return _own(chart, p)
    g, sig = chart["grahas"], chart["significators"]["by_planet"][p]
    in_its_star = [q for q in g if q != p and g[q]["nakshatra_lord"] == p]
    principal = g[p]["nakshatra_lord"] == p or not in_its_star
    occupied = {h for q in g for h in chart["significators"]["by_planet"][q]["occupied"]}
    houses = set(sig["occupied"]) if principal else set()
    houses |= {h for h in sig["owned"] if principal and h not in occupied}
    return houses or set(sig["occupied"])  # never leave a planet signifying nothing


@contextmanager
def patched(judge=None, own=None, predict=None):
    K.judge_lord, K.own_houses, K.predict = judge or _judge, own or _own, predict or _predict
    try:
        yield
    finally:
        K.judge_lord, K.own_houses, K.predict = _judge, _own, _predict


VARIANTS = {
    "baseline": {},
    "1 Taneja strength categories": {"judge": judge_taneja},
    "2 CSL in star of retrograde planet": {"predict": predict_retro_csl},
    "3 DBA lord in star of retrograde = delay": {"judge": judge_retro_star},
    "4 conjunction within 3°20' = agents": {"own": own_conjunct},
    "5 self-strength (drop secondary)": {"own": own_self_strength},
}


def base_rate(c, topic, center):
    """Duration-weighted share of the +-10 years around ``center`` rated favourable+ / strong."""
    tot = good = strong = 0
    for w in K.predict(c, topic, center - timedelta(days=3652), months=240)["windows"]:
        d = (date.fromisoformat(w["ends"]) - date.fromisoformat(w["starts"])).days
        tot += d
        good += d * (w["verdict"] in GOOD)
        strong += d * (w["verdict"] == "strong")
    return good / tot, strong / tot


def main():
    cl = TestClient(app)
    charts = []
    for label, dob, tob, (lat, lon), topic, when, dba in EVENTS:
        c = cl.post("/chart", json={"dob": dob, "tob": tob + ":00", "lat": lat, "lon": lon, "tz_name": "Asia/Kolkata"}).json()
        center = date.fromisoformat(when) if when else date.fromisoformat(dob) + timedelta(days=25 * 365)
        charts.append((label, c, topic, dob, when, dba, center))
    n = len(charts)
    rows = []
    for name, patch in VARIANTS.items():
        with patched(**patch):
            v = {lab: verdict_at_book_dba(c, t, dob, when, dba) for lab, c, t, dob, when, dba, _ in charts}
            b = [base_rate(c, t, cen) for _, c, t, _, _, _, cen in charts]
        fav, strong = sum(x in GOOD for x in v.values()), sum(x == "strong" for x in v.values())
        bf, bs = sum(x[0] for x in b) / n, sum(x[1] for x in b) / n
        rows.append((name, fav, strong, bf, bs, v))
        print(f"{name:42} favourable+ {fav:2}/{n} (base {bf:.0%}, lift ×{fav / n / bf:.2f})   "
              f"strong {strong:2}/{n} (base {bs:.0%}, lift ×{strong / n / bs:.2f})", flush=True)
    base = rows[0][5]
    print("\nEvents whose verdict changed versus baseline:")
    for name, *_, v in rows[1:]:
        ch = [f"{k}: {base[k]} -> {v[k]}" for k in v if v[k] != base[k]]
        print(f"  {name}: {'; '.join(ch) or 'none'}")


if __name__ == "__main__":
    main()
