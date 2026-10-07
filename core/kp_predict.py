"""KP prediction: is a matter promised, and in which daśā windows does it fructify?

Method (standard KP):
- Promise: the sub-lord of the matter's primary cusp must signify the houses that bring it about.
- What a period lord gives: the houses signified by its star lord (occupied and owned by the star
  lord), then by itself. Rahu/Ketu also act as agents of their sign lord.
- Whether it gives: the houses signified by the lord's sub lord. Favourable houses → yes;
  only the opposing houses → denial or obstacles.
- The antardasha (bhukti) lord carries most weight, then the pratyantar, then the mahadasha.
- Transit as trigger: Jupiter/Saturn moving through the favourable or opposing houses (KP cusps),
  or through the star of a supporting period lord, in that window.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS

from core.constants import NAKSHATRA_ARC, NAKSHATRA_LORDS, SIGN_LORDS
from core.kp import planet_house
from core.transits import transit_positions

# topic: (title, primary cusp, houses for, houses against). Career is as confirmed by the astrologer;
# the rest are standard KP groupings.
TOPICS = {
    "career": ("Career, job and promotion", 10, {2, 6, 10, 11}, {5, 9}),
    "marriage": ("Marriage", 7, {2, 7, 11}, {1, 6, 10}),
    "love": ("Love and relationships", 5, {5, 7, 11}, {1, 6, 10, 12}),
    "money": ("Money and gains", 11, {2, 6, 11}, {5, 8, 12}),
    "property": ("Property and vehicles", 4, {4, 11, 12}, {3, 5, 10}),
    "foreign": ("Foreign travel or settling abroad", 12, {3, 9, 12}, {2, 4, 11}),
    "children": ("Children", 5, {2, 5, 11}, {1, 4, 10}),
    "education": ("Education and exams", 4, {4, 9, 11}, {3, 8, 10}),
    "health": ("Health and recovery", 1, {1, 5, 11}, {6, 8, 12}),
    "litigation": ("Disputes and court cases", 6, {1, 6, 11}, {5, 8, 12}),
}
WEIGHT = {"maha": 1.0, "antar": 2.0, "praty": 1.5}
VALUE = {"supports": 1.0, "leans good": 0.5, "mixed": 0.0, "leans against": -0.5, "neutral": 0.0, "blocks": -1.0}


def _sig(chart: dict, p: str) -> dict:
    """KP houses a planet signifies: 'gives' (star-lord level first, then its own) and 'all'."""
    s = chart["significators"]["by_planet"][p]
    star = set(s["occupied_by_star_lord"]) | set(s["owned_by_star_lord"])
    own = set(s["occupied"]) | set(s["owned"])
    if p in ("Rahu", "Ketu"):  # nodes act as agents of their sign lord
        lord = SIGN_LORDS[chart["grahas"][p]["sign_index"]]
        ls = chart["significators"]["by_planet"][lord]
        own |= set(ls["occupied"]) | set(ls["owned"])
    return {"star": star, "own": own, "all": star | own}


def judge_lord(chart: dict, p: str, good: set, bad: set) -> dict:
    """What the planet gives (via its star lord) and whether it delivers (via its sub lord)."""
    g = chart["grahas"][p]
    sub = g["kp"]["sub_lord"]
    gives, decides = _sig(chart, p), _sig(chart, sub)
    g_for, g_against = sorted(gives["all"] & good), sorted(gives["all"] & bad)
    s_for, s_against = sorted(decides["all"] & good), sorted(decides["all"] & bad)
    net = len(s_for) - len(s_against)  # the sub lord decides: more houses for than against
    if g_for and net > 0:
        verdict = "supports"
    elif net < 0 or (g_against and not g_for):
        verdict = "blocks"
    elif g_for or s_for:  # the sub lord is undecided: lean by what the lord itself gives
        lean = len(g_for) - len(g_against)
        verdict = "leans good" if lean > 0 else "leans against" if lean < 0 else "mixed"
    else:
        verdict = "neutral"
    return {"lord": p, "star_lord": g["nakshatra_lord"], "sub_lord": sub, "gives": sorted(gives["all"]),
            "sub_signifies": sorted(decides["all"]), "for": sorted(set(g_for) | set(s_for)),
            "against": sorted(set(g_against) | set(s_against)), "verdict": verdict}


def promise(chart: dict, topic: str) -> dict:
    title, h, good, bad = TOPICS[topic]
    csl = chart["houses"][h - 1]["kp"]["sub_lord"]
    sig = _sig(chart, csl)["all"]
    f, a = sorted(sig & good), sorted(sig & bad)
    verdict = ("promised" if f and (h in sig or len(f) > len(a)) else
               "promised with obstacles" if f else "not clearly promised")
    return {"cusp": h, "cusp_sub_lord": csl, "csl_star_lord": chart["grahas"][csl]["nakshatra_lord"],
            "signifies": sorted(sig), "for": f, "against": a, "verdict": verdict}


def _cusps(chart: dict):
    return NS(cusps=[NS(house=c["house"], longitude=c["longitude"]) for c in chart["houses"]])


def transit_trigger(chart: dict, mid: date, lords: list[str], supporting: set, good: set, bad: set,
                    ayanamsha: str) -> tuple[float, list[str]]:
    tr = transit_positions(datetime(mid.year, mid.month, mid.day, 12, tzinfo=timezone.utc), ayanamsha)
    cusps, score, notes = _cusps(chart), 0.0, []
    for p in ("Jupiter", "Saturn"):
        lon = tr[p].longitude
        h = planet_house(lon, cusps)
        star = NAKSHATRA_LORDS[int(lon // NAKSHATRA_ARC)]
        if h in good:
            score += 0.5 if p == "Jupiter" else 0.25
            notes.append(f"{p} transits your {h}{_ord(h)} house (favourable)")
        elif h in bad:
            score -= 0.25 if p == "Jupiter" else 0.5
            notes.append(f"{p} transits your {h}{_ord(h)} house (opposing)")
        if star in supporting:
            score += 0.5
            notes.append(f"{p} moves through the star of {star}, a supporting period lord")
    return score, notes


def periods_in(chart: dict, start: date, end: date) -> list[dict]:
    out = []
    for md in chart["dasha"]:
        for ad in md.get("children", []):
            for pd in ad.get("children", []) or [ad]:
                s, e = date.fromisoformat(pd["start"][:10]), date.fromisoformat(pd["end"][:10])
                if e > start and s < end:
                    out.append({"maha": md["lord"], "antar": ad["lord"], "praty": pd["lord"], "starts": s, "ends": e})
    return out


def predict(chart: dict, topic: str, start: date | None = None, months: int = 24) -> dict:
    if topic not in TOPICS:
        raise ValueError(f"unknown topic: {topic}")
    title, h, good, bad = TOPICS[topic]
    start = start or datetime.now(timezone.utc).date()
    end = start + timedelta(days=round(months * 30.44))
    ayan = chart["meta"].get("ayanamsha", "krishnamurti")
    cache: dict[str, dict] = {}
    lord = lambda p: cache.setdefault(p, judge_lord(chart, p, good, bad))
    windows = []
    for per in periods_in(chart, start, end):
        js = {lvl: lord(per[lvl]) for lvl in ("maha", "antar", "praty")}
        score = sum(WEIGHT[l] * VALUE[j["verdict"]] for l, j in js.items())
        supporting = {j["lord"] for j in js.values() if j["verdict"] in ("supports", "leans good")}
        s, e = max(per["starts"], start), min(per["ends"], end)
        t_score, t_notes = transit_trigger(chart, s + (e - s) / 2, [per[l] for l in js], supporting, good, bad, ayan)
        score += t_score
        verdict = ("strong" if score >= 3 else "favourable" if score >= 1.5 else
                   "mixed" if score > -1 else "challenging")
        reasons = [f"{lvl_name} {j['lord']}: star lord {j['star_lord']} → gives houses {j['gives']}; "
                   f"sub lord {j['sub_lord']} → signifies {j['sub_signifies']}; {j['verdict']}"
                   for lvl_name, j in (("Mahadasha", js["maha"]), ("Antardasha", js["antar"]), ("Pratyantar", js["praty"]))]
        windows.append({"maha": per["maha"], "antar": per["antar"], "praty": per["praty"],
                        "starts": per["starts"].isoformat(), "ends": per["ends"].isoformat(),
                        "score": round(score, 2), "verdict": verdict, "reasons": reasons, "transit": t_notes})
    best = sorted([w for w in windows if w["verdict"] in ("strong", "favourable")], key=lambda w: -w["score"])[:3]
    hard = sorted([w for w in windows if w["verdict"] == "challenging"], key=lambda w: w["score"])[:2]
    return {"topic": topic, "title": title, "houses_for": sorted(good), "houses_against": sorted(bad),
            "promise": promise(chart, topic), "from": start.isoformat(), "to": end.isoformat(),
            "windows": windows, "best": [(w["starts"], w["ends"]) for w in best],
            "hardest": [(w["starts"], w["ends"]) for w in hard],
            "lords": {p: j for p, j in cache.items()}}


def _ord(n: int) -> str:
    return "th" if 10 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


KEYWORDS = {
    "career": r"career|job|promotion|work|office|boss|profession|business|employ|salary|appraisal|interview|resign",
    "marriage": r"marriage|marry|married|wedding|spouse|husband|wife|shaadi|rishta|engagement",
    "love": r"\blove|relationship|girlfriend|boyfriend|romance|crush|dating",
    "money": r"money|wealth|financ|income|gains?\b|invest|savings|profit|debt|loan|rich",
    "property": r"property|land|flat|apartment|house purchase|buy a house|vehicle|car\b",
    "foreign": r"abroad|foreign|visa|immigra|settle|relocat|overseas|\bpr\b|green card",
    "children": r"child|children|baby|pregnan|conceive|\bson\b|daughter|kids?\b",
    "education": r"exam|study|studies|education|admission|degree|college|university|course",
    "health": r"health|illness|disease|surgery|recover|hospital|sick",
    "litigation": r"court|lawsuit|\bcase\b|dispute|legal|litigation",
}


def topics_for(question: str) -> list[str]:
    import re
    q = question.lower()
    return [t for t, pat in KEYWORDS.items() if re.search(pat, q)][:2]


def brief(result: dict) -> str:
    """Compact text the chat model explains; every verdict and date in it is computed."""
    p = result["promise"]
    lines = [f"KP PREDICTION — {result['title']} (houses for {','.join(map(str, result['houses_for']))}; "
             f"against {','.join(map(str, result['houses_against']))})",
             f"Promise: {p['cusp']}th cusp sub lord {p['cusp_sub_lord']} (star lord {p['csl_star_lord']}) signifies "
             f"{','.join(map(str, p['signifies']))} → {p['verdict']}.",
             "Windows (maha/antar/pratyantar: verdict, score):"]
    for w in result["windows"]:
        lords = result["lords"]
        why = "; ".join(f"{l} {lords[l]['verdict']} (gives {','.join(map(str, lords[l]['gives']))}, sub {lords[l]['sub_lord']})"
                        for l in dict.fromkeys([w["antar"], w["praty"]]))
        lines.append(f"- {w['starts']} to {w['ends']} {w['maha']}/{w['antar']}/{w['praty']}: {w['verdict'].upper()} "
                     f"({w['score']}). {why}." + (f" Transit: {'; '.join(w['transit'])}." if w["transit"] else ""))
    return "\n".join(lines)
