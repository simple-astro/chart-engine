"""Nadi/KP prediction: is a matter promised, and in which daśā windows does it happen?

Method (Umang Taneja, Nadi Astrology — Accurate Predictive Methodology):
- Every planet is read at three levels — the planet itself, its nakshatra (star) lord and its sub
  lord — and each level signifies the houses that planet occupies and owns. Sub lord is strongest,
  then the nakshatra lord, then the planet.
- Rahu/Ketu signify the houses of the planets they are conjunct with, the planets aspecting them,
  their sign lord, and the house they sit in.
- A level supports a matter by the houses of its combination and is weakened by the negating
  houses (generally the 12th from each). Facilitating houses neither add nor subtract.
- Promise: the sub lord of the matter's main cusp must signify the combination.
- Timing: the Dasa lord is strongest and must allow the event; then the Bhukti, then the Antar.
- Significator (karaka) planets: for some matters one of the DBA lords must be the karaka, or be
  conjunct with / aspected by it (e.g. Mars or Saturn for property, Venus for vehicles).
- Transit as trigger: Jupiter/Saturn through the combination's houses, or through the star of a
  supporting period lord.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS

from core.constants import NAKSHATRA_ARC, NAKSHATRA_LORDS, SIGN_LORDS
from core.kp import planet_house
from core.transits import transit_positions
from core.yogas import aspects

SEPARATIVES = {"Sun", "Saturn", "Rahu", "Ketu"}

# key: title, main cusp, houses of the combination, negating houses, karaka planets, karaka required,
# kind ("event" = hoped for, "risk" = something to watch). From the astrologer's summary table; career's
# negating houses (5, 9) were confirmed by the astrologer.
TOPICS = {
    "marriage": ("Marriage", 7, {2, 7, 11}, {1, 6, 10}, {"Venus"}, False, "event"),
    "love": ("Love affair", 5, {5, 11}, {6}, {"Venus"}, False, "event"),
    "career": ("Job, promotion and career", 10, {2, 6, 10, 11}, {5, 9}, {"Saturn"}, False, "event"),
    "business": ("Business", 7, {2, 7, 10, 11}, {1, 6, 9}, {"Mercury"}, False, "event"),
    "job_change": ("Changing job or business", 10, {5, 9}, {2, 6, 11}, SEPARATIVES, True, "event"),
    "money": ("Money and gains", 11, {2, 6, 11}, {1, 5, 10}, {"Jupiter"}, False, "event"),
    "property": ("Buying property", 4, {4, 11, 12}, {3, 10}, {"Mars", "Saturn"}, True, "event"),
    "property_sale": ("Selling property", 4, {3, 5, 10}, {2, 4, 9}, {"Mars", "Saturn"}, True, "event"),
    "vehicle": ("Buying a vehicle", 4, {4, 11, 12}, {10}, {"Venus"}, True, "event"),
    "residence": ("Changing residence", 4, {3, 5}, {2, 4, 11}, SEPARATIVES, True, "event"),
    "foreign": ("Foreign travel or settling abroad", 12, {3, 9, 12}, {2, 4, 11}, SEPARATIVES, True, "event"),
    "return_home": ("Coming back home", 4, {2, 4, 11}, {3, 9, 12}, set(), False, "event"),
    "education": ("Education and marks", 4, {4, 9, 11}, {6, 8, 12}, {"Mercury", "Jupiter"}, False, "event"),
    "exams": ("Competitive exams and interviews", 11, {4, 6, 9, 11}, {8, 12}, {"Mercury", "Jupiter"}, False, "event"),
    "awards": ("Awards and prizes", 11, {6, 10, 11}, {5, 8, 12}, {"Jupiter", "Venus"}, False, "event"),
    "children": ("Children", 5, {2, 5, 11}, {1, 4, 10}, {"Jupiter"}, False, "event"),
    "health": ("Good health and recovery", 1, {1, 5, 9, 11}, {6, 8, 12}, {"Jupiter"}, False, "event"),
    "litigation_win": ("Winning a dispute or court case", 6, {1, 6, 10, 11}, {5, 8, 12}, set(), False, "event"),
    "illness": ("Illness", 6, {1, 6, 8, 12}, {5, 11}, {"Saturn"}, False, "risk"),
    "accident": ("Accidents and injury", 8, {1, 4, 8, 12}, {5, 11}, {"Rahu", "Ketu"}, True, "risk"),
    "career_loss": ("Loss in job or business", 10, {5, 8, 12}, {10, 11}, set(), False, "risk"),
    "divorce": ("Separation or divorce", 7, {1, 6, 10}, {2, 7, 11}, SEPARATIVES, True, "risk"),
    "litigation": ("Getting into a dispute or court case", 6, {6, 8, 12}, {11}, {"Rahu", "Ketu", "Saturn"}, True, "risk"),
}
# Houses the book calls facilitators: they help the combination when it is present (and, for marriage,
# 5 and 9 always help). Property/vehicle: 6 = on loan, 8 = through PF/insurance; 3 helps vehicles.
FACILITATORS = {"marriage": {5, 8, 9, 12}, "children": {9}, "property": {6, 8}, "vehicle": {3, 6, 8},
                "education": {2, 3, 5}, "exams": {3, 5}, "love": {8, 12}}
# "Venus is capable of promising marriage in its DBA even if it doesn't signify 2,7,11";
# "the mere presence of Jupiter in DBA results into child birth".
NATURAL = {"marriage": "Venus", "children": "Jupiter"}
# Risks need a real combination (the book: "6, 8 or 12 alone does not result in litigation"): at least two
# houses of it, plus any houses the combination cannot do without (illness always involves 1 and 6).
RISK_RULES = {"illness": {"all": {1, 6}}, "accident": {"any": {8}}, "career_loss": {"any": {5}},
              "divorce": {}, "litigation": {}}
WEIGHT_LEVEL = {"planet": 1.0, "nakshatra": 1.5, "sub": 2.0}   # sub lord strongest
WEIGHT_DBA = {"maha": 2.0, "antar": 1.5, "praty": 1.0}        # Dasa lord strongest
VALUE = {"supports": 1.0, "leans good": 0.5, "mixed": 0.0, "against": -0.5, "blocks": -1.0}
RISK_LABEL = {"strong": "take extra care", "favourable": "take care", "mixed": "mild", "challenging": "low"}


def own_houses(chart: dict, p: str) -> set[int]:
    """Houses a planet signifies by itself: where it sits and the cusps it owns (Rahu/Ketu as agents)."""
    sig = chart["significators"]["by_planet"][p]
    houses = set(sig["occupied"]) | set(sig["owned"])
    if p in ("Rahu", "Ketu"):
        signs = {q: g["sign_index"] for q, g in chart["grahas"].items()}
        asp = aspects(signs, chart["lagna"]["sign_index"])
        agents = {q for q in signs if q not in ("Rahu", "Ketu") and
                  (signs[q] == signs[p] or p in asp[q]["planets"])}
        agents.add(SIGN_LORDS[signs[p]])
        for q in agents:
            s = chart["significators"]["by_planet"][q]
            houses |= set(s["occupied"]) | set(s["owned"])
    return houses


# Which reading of a planet's significations to use (kept switchable so methods can be backtested):
#   "nadi": planet / nakshatra lord / sub lord each signify their own houses (Taneja).
#   "kp":   as nadi, but the sub lord is read through KP's four-fold significations (its star lord's houses too).
#   "kp4":  Krishnamurti's strength order — star lord's occupied house > star lord's owned houses >
#           the planet's own occupied house > its owned houses — with the sub lord read the same way.
METHOD = "kp"  # best on the dated-event backtest (strong windows x1.5 over chance)
KP4_W = {"occupied_by_star_lord": 1.0, "owned_by_star_lord": 0.75, "occupied": 0.5, "owned": 0.4}


def fourfold(chart: dict, p: str) -> set[int]:
    return own_houses(chart, p) | own_houses(chart, chart["grahas"][p]["nakshatra_lord"])


def kp4_net(chart: dict, p: str, good: set, bad: set) -> float:
    s = chart["significators"]["by_planet"][p]
    w: dict[int, float] = {}
    for k, wt in KP4_W.items():
        for h in s[k]:
            w[h] = max(w.get(h, 0.0), wt)
    if p in ("Rahu", "Ketu"):
        for h in own_houses(chart, p):
            w.setdefault(h, 0.5)
    return sum(v for h, v in w.items() if h in good) - sum(v for h, v in w.items() if h in bad)


def _combo(s: set, good: set, rule: dict) -> bool:
    return len(s & good) >= 2 and rule.get("all", set()) <= s and (not rule.get("any") or bool(rule["any"] & s))


def judge_lord(chart: dict, p: str, good: set, bad: set, risk: dict | None = None, fac: set | None = None) -> dict:
    """Planet, nakshatra lord and sub lord each signify their own houses; the sub lord weighs most.
    For a risk, the combination must be formed within a level or across nakshatra + sub (or planet + nakshatra)."""
    g = chart["grahas"][p]
    lords = {"planet": p, "nakshatra": g["nakshatra_lord"], "sub": g["kp"]["sub_lord"]}
    levels, score = {}, 0.0
    for lvl, q in lords.items():
        h = fourfold(chart, q) if (METHOD == "kp" and lvl == "sub") else own_houses(chart, q)
        if risk is None and METHOD != "kp4":
            v = len(h & good) - len(h & bad)
            if fac and h & fac and not h & bad:
                v += 0.5  # facilitators support when nothing negates at that level
            score += WEIGHT_LEVEL[lvl] * max(-2, min(2, v))
        levels[lvl] = {"lord": q, "houses": sorted(h), "for": sorted(h & good), "against": sorted(h & bad)}
    if risk is None and METHOD == "kp4":
        clip = lambda x: max(-2.0, min(2.0, x))
        score = 1.5 * clip(kp4_net(chart, p, good, bad)) + 2.0 * clip(kp4_net(chart, lords["sub"], good, bad))
        if fac:
            score += 0.5 * bool(own_houses(chart, lords["sub"]) & fac and not own_houses(chart, lords["sub"]) & bad)
    if risk is not None:
        H = {l: set(v["houses"]) for l, v in levels.items()}
        score = (4.0 if _combo(H["sub"], good, risk) or _combo(H["nakshatra"], good, risk) else
                 3.0 if _combo(H["nakshatra"] | H["sub"], good, risk) else
                 2.0 if _combo(H["planet"] | H["nakshatra"], good, risk) else 0.0)
        score -= 1.5 if H["sub"] & bad else 0.0  # the sub lord signifying the remedy houses (e.g. 5, 11) eases it
    verdict = ("supports" if score >= 3 else "leans good" if score >= 1 else "mixed" if score > -1
               else "against" if score > -3 else "blocks")
    return {"lord": p, "star_lord": lords["nakshatra"], "sub_lord": lords["sub"], "levels": levels,
            "score": round(score, 2), "verdict": verdict}


def promise(chart: dict, topic: str) -> dict:
    title, h, good, bad, *_ = TOPICS[topic]
    csl = chart["houses"][h - 1]["kp"]["sub_lord"]
    j = judge_lord(chart, csl, good, bad, RISK_RULES.get(topic) if TOPICS[topic][6] == "risk" else None,
                   FACILITATORS.get(topic))
    verdict = {"supports": "promised", "leans good": "promised", "mixed": "promised with obstacles"}.get(
        j["verdict"], "not clearly promised")
    if TOPICS[topic][6] == "risk":
        verdict = {"promised": "indicated", "promised with obstacles": "possible"}.get(verdict, "not strongly indicated")
    sub = j["levels"]["sub"]
    return {"cusp": h, "cusp_sub_lord": csl, "csl_star_lord": j["star_lord"], "signifies": sub["houses"],
            "for": sub["for"], "against": sub["against"], "verdict": verdict, "judgement": j}


def _cusps(chart: dict):
    return NS(cusps=[NS(house=c["house"], longitude=c["longitude"]) for c in chart["houses"]])


def transit_trigger(chart: dict, mid: date, supporting: set, good: set, bad: set, ayanamsha: str) -> tuple[float, list[str]]:
    tr = transit_positions(datetime(mid.year, mid.month, mid.day, 12, tzinfo=timezone.utc), ayanamsha)
    cusps, score, notes = _cusps(chart), 0.0, []
    for p in ("Jupiter", "Saturn"):
        lon = tr[p].longitude
        h = planet_house(lon, cusps)
        star = NAKSHATRA_LORDS[int(lon // NAKSHATRA_ARC)]
        if h in good:
            score += 0.5 if p == "Jupiter" else 0.25
            notes.append(f"{p} transits your {h}{_ord(h)} house (part of the combination)")
        elif h in bad:
            score -= 0.25 if p == "Jupiter" else 0.5
            notes.append(f"{p} transits your {h}{_ord(h)} house (negating)")
        if star in supporting:
            score += 0.5
            notes.append(f"{p} moves through the star of {star}, a supporting period lord")
    return score, notes


def karaka_present(chart: dict, lords: list[str], karakas: set) -> str | None:
    """A DBA lord that is a karaka, or is conjunct with / aspected by one."""
    if not karakas:
        return None
    signs = {q: g["sign_index"] for q, g in chart["grahas"].items()}
    asp = aspects(signs, chart["lagna"]["sign_index"])
    for l in lords:
        if l in karakas:
            return f"{l} is itself the significator"
        for k in karakas:
            if k != l and (signs[k] == signs[l] or l in asp[k]["planets"]):
                return f"{l} is {'with' if signs[k] == signs[l] else 'aspected by'} the significator {k}"
    return None


def periods_in(chart: dict, start: date, end: date) -> list[dict]:
    out = []
    for md in chart["dasha"]:
        for ad in md.get("children", []):
            for pd in ad.get("children", []) or [ad]:
                s, e = date.fromisoformat(pd["start"][:10]), date.fromisoformat(pd["end"][:10])
                if e > start and s < end:
                    out.append({"maha": md["lord"], "antar": ad["lord"], "praty": pd["lord"], "starts": s, "ends": e})
    return out


def lord_verdict(chart: dict, topic: str, p: str) -> dict:
    """How one period lord judges one life matter at planet / star / sub level (natural significator included)."""
    _, _, good, bad, _, _, kind = TOPICS[topic]
    j = judge_lord(chart, p, good, bad, RISK_RULES.get(topic, {}) if kind == "risk" else None, FACILITATORS.get(topic))
    if NATURAL.get(topic) == p and VALUE[j["verdict"]] < VALUE["leans good"]:
        j = {**j, "verdict": "leans good", "note": f"{p} is the natural significator"}
    return j


def predict(chart: dict, topic: str, start: date | None = None, months: int = 24) -> dict:
    if topic not in TOPICS:
        raise ValueError(f"unknown topic: {topic}")
    title, h, good, bad, karakas, required, kind = TOPICS[topic]
    start = start or datetime.now(timezone.utc).date()
    end = start + timedelta(days=round(months * 30.44))
    ayan = chart["meta"].get("ayanamsha", "krishnamurti")
    cache: dict[str, dict] = {}
    rule = RISK_RULES.get(topic, {}) if kind == "risk" else None
    fac = FACILITATORS.get(topic)

    def lord(p):
        if p not in cache:
            cache[p] = lord_verdict(chart, topic, p)
        return cache[p]
    windows = []
    for per in periods_in(chart, start, end):
        js = {lvl: lord(per[lvl]) for lvl in ("maha", "antar", "praty")}
        score = sum(WEIGHT_DBA[l] * VALUE[j["verdict"]] for l, j in js.items())
        supporting = {j["lord"] for j in js.values() if j["verdict"] in ("supports", "leans good")}
        s, e = max(per["starts"], start), min(per["ends"], end)
        t_score, notes = transit_trigger(chart, s + (e - s) / 2, supporting, good, bad, ayan)
        score += t_score
        kar = karaka_present(chart, [per[l] for l in js], karakas)
        if kar:
            score += 0.5
            notes.append(f"Significator: {kar}")
        # The book's timing sequence: the Dasa must allow, the Bhukti pinpoints, the Antar times the event.
        ok = lambda j: j["verdict"] in ("supports", "leans good")
        neg = lambda j: j["verdict"] in ("against", "blocks")
        if js["maha"]["verdict"] == "blocks":
            verdict = "challenging" if neg(js["antar"]) else "mixed"
        elif ok(js["antar"]) and ok(js["praty"]):
            verdict = "strong"
        elif ok(js["antar"]) or (ok(js["maha"]) and ok(js["praty"])):
            verdict = "favourable"
        elif neg(js["antar"]) and neg(js["praty"]):
            verdict = "challenging"
        else:
            verdict = "mixed"
        # The Dasa lord must allow the event, then the Bhukti; a required karaka must be involved.
        cap = None
        if js["maha"]["verdict"] == "blocks":
            cap = "the Dasa lord does not allow it"
        elif js["antar"]["verdict"] == "blocks":
            cap = "the Bhukti lord does not allow it"
        elif required and not kar:
            cap = f"no significator ({', '.join(sorted(karakas))}) is involved"
        if cap and verdict in ("strong", "favourable"):
            verdict = "mixed"
            notes.append(f"Held back: {cap}")
        reasons = []
        for name, j in (("Dasa", js["maha"]), ("Bhukti", js["antar"]), ("Antar", js["praty"])):
            L = j["levels"]
            reasons.append(f"{name} {j['lord']}: planet {_hs(L['planet']['houses'])}, nakshatra {L['nakshatra']['lord']} "
                           f"{_hs(L['nakshatra']['houses'])}, sub {L['sub']['lord']} {_hs(L['sub']['houses'])} → {j['verdict']}")
        windows.append({"maha": per["maha"], "antar": per["antar"], "praty": per["praty"],
                        "starts": per["starts"].isoformat(), "ends": per["ends"].isoformat(),
                        "score": round(score, 2), "verdict": verdict, "reasons": reasons, "transit": notes})
    best = sorted([w for w in windows if w["verdict"] in ("strong", "favourable")], key=lambda w: -w["score"])[:3]
    hard = sorted([w for w in windows if w["verdict"] == "challenging"], key=lambda w: w["score"])[:2]
    return {"topic": topic, "title": title, "kind": kind, "houses_for": sorted(good), "houses_against": sorted(bad),
            "significators": sorted(karakas), "significator_required": required,
            "promise": promise(chart, topic), "from": start.isoformat(), "to": end.isoformat(),
            "windows": windows, "best": [(w["starts"], w["ends"]) for w in best],
            "hardest": [(w["starts"], w["ends"]) for w in hard], "lords": dict(cache)}


def _hs(h: list[int]) -> str:
    return ",".join(map(str, h)) or "none"


def _ord(n: int) -> str:
    return "th" if 10 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


KEYWORDS = {
    "career": r"career|job|promotion|work|office|boss|profession|employ|salary|appraisal|interview",
    "business": r"business|startup|shop|trade|partnership firm",
    "job_change": r"change (my |of )?job|switch|resign|new job|leave (my |the )?job|quit",
    "marriage": r"marriage|marry|married|wedding|spouse|husband|wife|shaadi|rishta|engagement",
    "divorce": r"divorce|separation|separate",
    "love": r"\blove|relationship|girlfriend|boyfriend|romance|crush|dating",
    "money": r"money|wealth|financ|income|gains?\b|invest|savings|profit|rich",
    "property": r"property|land|plot|flat|apartment|buy a house|house purchase",
    "property_sale": r"sell (my |the )?(house|property|flat|plot|land)",
    "vehicle": r"vehicle|\bcar\b|bike|scooter",
    "residence": r"shift(ing)? house|move house|change (of )?residence|relocat",
    "foreign": r"abroad|foreign|visa|immigra|settle|overseas|\bpr\b|green card",
    "return_home": r"come back home|return (home|to india)|back to india",
    "education": r"study|studies|education|marks|degree|college|university|course",
    "exams": r"exam|competitive|entrance|interview|selection",
    "awards": r"award|prize|recognition",
    "children": r"child|children|baby|pregnan|conceive|\bson\b|daughter|kids?\b",
    "health": r"health|recover|well-being",
    "illness": r"illness|disease|surgery|sick|hospital",
    "accident": r"accident|injur",
    "litigation": r"court|lawsuit|\bcase\b|dispute|legal|litigation",
}


def topics_for(question: str) -> list[str]:
    q = question.lower()
    found = [t for t, pat in KEYWORDS.items() if re.search(pat, q)]
    if "litigation" in found and re.search(r"\bwin\b|winning", q):
        found[found.index("litigation")] = "litigation_win"
    return found[:2]


def brief(result: dict) -> str:
    """Compact text the chat model explains; every verdict and date in it is computed."""
    p, risk = result["promise"], result["kind"] == "risk"
    label = (lambda v: RISK_LABEL[v].upper()) if risk else (lambda v: v.upper())
    lines = [f"NADI PREDICTION — {result['title']} (combination {','.join(map(str, result['houses_for']))}; "
             f"negating {','.join(map(str, result['houses_against']))}"
             + (f"; significator {'/'.join(result['significators'])}" if result["significators"] else "") + ")"
             + (" — this is a RISK reading: a strong window means more risk, not good news." if risk else ""),
             f"Promise: {p['cusp']}th cusp sub lord {p['cusp_sub_lord']} signifies {','.join(map(str, p['signifies']))} "
             f"→ {p['verdict']}.",
             "Windows (dasa/bhukti/antar: verdict):"]
    for w in result["windows"]:
        lj = result["lords"]
        why = "; ".join(f"{l} {lj[l]['verdict']} (sub {lj[l]['sub_lord']})" for l in dict.fromkeys([w["maha"], w["antar"], w["praty"]]))
        lines.append(f"- {w['starts']} to {w['ends']} {w['maha']}/{w['antar']}/{w['praty']}: {label(w['verdict'])} "
                     f"({w['score']}). {why}." + (f" {'; '.join(w['transit'])}." if w["transit"] else ""))
    return "\n".join(lines)


# ----- day-level timing (the book's transit rules) -----
FAST = {"Sun", "Mercury", "Venus", "Mars", "Moon"}
ORB = 1.0  # "within one degree"


def significators(chart: dict, topic: str) -> dict[str, dict]:
    """Planets that signify the event (their three-level reading supports it)."""
    _, _, good, bad, _, _, kind = TOPICS[topic]
    rule = RISK_RULES.get(topic, {}) if kind == "risk" else None
    js = {p: judge_lord(chart, p, good, bad, rule, FACILITATORS.get(topic)) for p in chart["grahas"]}
    return {p: j for p, j in js.items() if j["verdict"] in ("supports", "leans good")}


def _sep(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def day_triggers(chart: dict, topic: str, d: date, tz_name: str = "UTC", names: set | None = None,
                 antar_lord: str | None = None) -> tuple[list[str], bool]:
    """The book's day-level transit triggers on one date, and whether a fast planet is involved."""
    from itertools import combinations
    from zoneinfo import ZoneInfo
    good = TOPICS[topic][2]
    names = set(significators(chart, topic)) if names is None else names
    natal = {p: chart["grahas"][p]["longitude"] for p in names}
    cusps = {c["house"]: c["longitude"] for c in chart["houses"] if c["house"] in good}
    ayan = chart["meta"].get("ayanamsha", "krishnamurti")
    tr = transit_positions(datetime(d.year, d.month, d.day, 12, tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc), ayan)
    lon = {p: g.longitude for p, g in tr.items()}
    hits, fast = [], False
    for p in names:
        for q in names:
            if _sep(lon[p], natal[q]) <= ORB:
                hits.append(f"{p} transits over your natal {q}" if p != q else f"{p} returns to its natal degree")
                fast |= p in FAST
        for h, cl in cusps.items():
            if _sep(lon[p], cl) <= ORB:
                hits.append(f"{p} crosses your {h}{_ord(h)} cusp")
                fast |= p in FAST
    for a, b in combinations(sorted(names - {"Moon"}), 2):
        if int(lon[a] // 30) == int(lon[b] // 30) and _sep(lon[a], lon[b]) <= ORB:
            hits.append(f"{a} and {b} conjoin within a degree")
            fast |= bool({a, b} & FAST)
    if "Moon" in names:
        with_moon = [p for p in names - {"Moon"} if int(lon[p] // 30) == int(lon["Moon"] // 30)]
        if len(with_moon) >= 3:
            hits.append("the Moon joins " + ", ".join(sorted(with_moon)))
            fast = True
    if antar_lord:
        star = NAKSHATRA_LORDS[int(lon[antar_lord] // NAKSHATRA_ARC)]
        if star in names:
            hits.append(f"Antar lord {antar_lord} moves through the star of {star}")
    return hits, fast


def event_days(chart: dict, topic: str, start: date | None = None, days: int = 90, tz_name: str = "UTC",
               limit: int = 7) -> dict:
    """Most likely days in the next ``days`` days, inside windows the DBA allows, with the transit reasons."""
    if topic not in TOPICS:
        raise ValueError(f"unknown topic: {topic}")
    days = max(1, min(366, days))
    start = start or datetime.now(timezone.utc).date()
    names = set(significators(chart, topic))
    plan = predict(chart, topic, start, months=days / 30.44 + 1)
    found = []
    for i in range(days):
        d = start + timedelta(days=i)
        w = next((x for x in plan["windows"] if x["starts"] <= d.isoformat() < x["ends"]), None)
        if not w or w["verdict"] not in ("strong", "favourable"):
            continue
        hits, fast = day_triggers(chart, topic, d, tz_name, names, w["praty"])
        if hits and fast:
            found.append({"date": d.isoformat(), "score": len(hits) + (1 if w["verdict"] == "strong" else 0),
                          "period": f"{w['maha']}/{w['antar']}/{w['praty']}", "window": w["verdict"], "hits": hits})
    best = []  # strongest day of each cluster (transits linger over neighbouring days)
    for x in sorted(found, key=lambda x: (-x["score"], x["date"])):
        if all(abs((date.fromisoformat(x["date"]) - date.fromisoformat(y["date"])).days) > 2 for y in best):
            best.append(x)
        if len(best) == limit:
            break
    return {"topic": topic, "title": TOPICS[topic][0], "kind": TOPICS[topic][6], "from": start.isoformat(),
            "days_checked": days, "significators": sorted(names), "candidate_days": len(found),
            "days": sorted(best, key=lambda x: x["date"])}
