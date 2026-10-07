"""Guardrail: check an answer's astrological claims against the computed chart before it is shown.

Each sentence is scanned for claims a reader would take as fact — dignity, retrograde, combust,
Neecha Bhanga, house placement, lordship, drishti, sign, yogas, Sade Sati, the running daśā, and
dates — and each claim is compared with the synthesised chart (natal, KP and today's transits)
plus anything the chat tools returned. Negated or conditional sentences are skipped, and every
check accepts any reading the data supports, so a flagged claim is a real contradiction.
"""
from __future__ import annotations

import json
import re
from datetime import date

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
ALIAS = {"surya": "Sun", "chandra": "Moon", "mangal": "Mars", "budh": "Mercury", "budha": "Mercury", "guru": "Jupiter",
         "brihaspati": "Jupiter", "shukra": "Venus", "shani": "Saturn", "sun": "Sun", "moon": "Moon", "mars": "Mars",
         "mercury": "Mercury", "jupiter": "Jupiter", "venus": "Venus", "saturn": "Saturn", "rahu": "Rahu", "ketu": "Ketu"}
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
         "Aquarius", "Pisces"]
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
YOGAS = {"raja yoga": "Raja yoga", "dhana yoga": "Dhana yoga", "gaja kesari": "Gaja Kesari", "gajakesari": "Gaja Kesari",
         "budha-aditya": "Budha-Aditya", "budhaditya": "Budha-Aditya", "budha aditya": "Budha-Aditya",
         "chandra-mangala": "Chandra-Mangala", "chandra mangala": "Chandra-Mangala", "ruchaka": "Ruchaka",
         "bhadra yoga": "Bhadra", "hamsa": "Hamsa", "malavya": "Malavya", "sasa yoga": "Sasa", "shasha": "Sasa",
         "kemadruma": "Kemadruma", "kaal sarp": "Kaal Sarp", "kalsarp": "Kaal Sarp", "kala sarpa": "Kaal Sarp",
         "viparita": "Viparita", "harsha": "Harsha", "sarala": "Sarala", "vimala": "Vimala", "yogakaraka": "Yogakaraka"}
NEG = re.compile(r"\b(not|no|isn't|aren't|wasn't|never|neither|nor|without|unless|if|whether|lacks?|absence)\b|n't\b", re.I)
PLANET_RE = re.compile(r"\b(" + "|".join(ALIAS) + r")\b", re.I)
ORD_RE = re.compile(r"\b(1[0-2]|[1-9])(?:st|nd|rd|th)\b(?:\s+house)?", re.I)
THEME_HOUSE = {"self": 1, "personality": 1, "wealth": 2, "family": 2, "money": 2, "courage": 3, "siblings": 3,
               "home": 4, "mother": 4, "property": 4, "children": 5, "education": 5, "romance": 5, "enemies": 6,
               "debts": 6, "disease": 6, "service": 6, "marriage": 7, "partnership": 7, "spouse": 7, "longevity": 8,
               "luck": 9, "fortune": 9, "dharma": 9, "father": 9, "career": 10, "profession": 10, "status": 10,
               "gains": 11, "income": 11, "expenses": 12, "losses": 12, "foreign": 12, "moksha": 12}
THEME_RE = re.compile(r"\b(" + "|".join(THEME_HOUSE) + r")\s+house\b|\bhouse\s+of\s+(" + "|".join(THEME_HOUSE) + r")\b", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2},\s+)?(\d{4})\b", re.I)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def facts_from(synth: dict, chart: dict, extra: list | None = None, kp: dict | None = None) -> dict:
    """Everything a claim may legitimately match: natal, KP, from-Moon and transit readings."""
    L = SIGNS.index(synth["lagna"]["sign"])
    moon = SIGNS.index(synth["moon"]["sign"])
    P = {}
    for p, d in synth["planets"].items():
        s = SIGNS.index(d["sign"])
        tr = synth["transits_now"].get(p, {})
        P[p] = {"dignity": d["dignity"], "sign": {d["sign"]} | ({tr["sign"]} if tr else set()),
                "houses": {d["h"], chart["grahas"][p].get("house"), (s - moon) % 12 + 1}
                          | ({tr["h_from_lagna"], tr["h_from_moon"]} if tr else set()),
                "owns": set(d["owns"]), "aspects": set(d["aspects_h"]) | set(tr.get("aspects_h", [])),
                "retro": "retrograde" in d.get("flags", []) or tr.get("retrograde", False) or p in ("Rahu", "Ketu"),
                "combust": "combust" in d.get("flags", []),
                "nb": str(d.get("neecha_bhanga", "")).startswith("cancelled")}
    blob = json.dumps({"s": synth, "d": chart.get("dasha", []), "x": extra or []})
    months = {(int(y), int(m)) for y, m in re.findall(r"(\d{4})-(\d{2})", blob)}
    yogas = {y.split(" [")[0].split(" (")[0] for y in synth.get("yogas", [])}
    yogas |= {y.split(" (")[1].rstrip(")") for y in synth.get("yogas", []) if " (" in y.split(" [")[0]}
    if any("Harsha" in y or "Sarala" in y or "Vimala" in y for y in synth.get("yogas", [])):
        yogas.add("Viparita")
    d = synth.get("dasha", {})
    ym = lambda iso: int(iso[:4]) * 12 + int(iso[5:7])
    span = lambda node, **k: {"lord": node["lord"], "a": ym(node["start"]), "b": ym(node["end"]),
                              "s": date.fromisoformat(node["start"][:10]), "e": date.fromisoformat(node["end"][:10]),
                              "from": node["start"][:7], "to": node["end"][:7], **k}
    spans = {"maha": [], "antar": [], "praty": []}
    for md in chart.get("dasha", []):
        spans["maha"].append(span(md))
        for ad in md.get("children", []):
            spans["antar"].append(span(ad, maha=md["lord"]))
            for pd in ad.get("children", []):
                spans["praty"].append(span(pd, maha=md["lord"], antar=ad["lord"]))
    kp_windows = {t: [{"s": date.fromisoformat(w["starts"]), "e": date.fromisoformat(w["ends"]), "verdict": w["verdict"],
                       "label": f"{w['antar']}/{w['praty']}"} for w in r["windows"]] for t, r in (kp or {}).items()}
    return {"kp": kp_windows, "kp_kind": {t: r.get("kind", "event") for t, r in (kp or {}).items()}, "spans": spans, "today": date.fromisoformat(synth["today"]), "planets": P, "lagna": synth["lagna"]["sign"], "months": months, "yogas": yogas,
            "sade_sati": "sade_sati" in synth["transits_now"],
            "maha": (d.get("maha") or {}).get("lord"), "antar": (d.get("antar") or {}).get("lord")}


def _planet_near(sent: str, pos: int) -> str | None:
    """The planet a keyword at ``pos`` is about: nearest mention before it, else just after it."""
    before = [m for m in PLANET_RE.finditer(sent) if m.end() <= pos]
    if before:
        return ALIAS[before[-1].group(1).lower()]
    after = PLANET_RE.search(sent, pos)
    return ALIAS[after.group(1).lower()] if after else None


def _in_life(ym: tuple[int, int], months: set) -> bool:
    """Dates tied to a named period get a strict check elsewhere; a stray date only has to fall within
    the native's lifetime daśā span (anything else is invented)."""
    n = ym[0] * 12 + ym[1]
    span = [y * 12 + m for y, m in months]
    return min(span) - 1 <= n <= max(span) + 1


def check(text: str, facts: dict) -> list[dict]:
    issues = []
    P = facts["planets"]

    def flag(sent, claim, truth):
        issues.append({"sentence": sent, "claim": claim, "truth": truth})

    for sent in sentences(text):
        low = sent.lower()
        clauses = [(m.start(), m.end()) for m in re.finditer(r"[^,;:—–()]+", sent)]
        negated = lambda pos: any(a <= pos < b and NEG.search(sent[a:b]) for a, b in clauses)
        for word, want in (("exalted", "exalted"), ("debilitated", "debilitated")):
            for m in re.finditer(word, low):
                p = None if negated(m.start()) else _planet_near(sent, m.start())
                if p and p in P and P[p]["dignity"] != want:
                    flag(sent, f"{p} {word}", f"{p} is {P[p]['dignity']} in this chart, not {word}")
        for m in re.finditer(r"own sign|in its own", low):
            p = None if negated(m.start()) else _planet_near(sent, m.start())
            if p and p in P and P[p]["dignity"] != "own":
                flag(sent, f"{p} in own sign", f"{p} is {P[p]['dignity']}, not in its own sign")
        for word, key in (("retrograde", "retro"), ("combust", "combust")):
            for m in re.finditer(word, low):
                p = None if negated(m.start()) else _planet_near(sent, m.start())
                if p and p in P and not P[p][key]:
                    flag(sent, f"{p} {word}", f"{p} is not {word} (natally or in today's transit)")
        for m in re.finditer(r"neecha ?bhanga|debilitation is cancelled|cancelled debilitation", low):
            p = None if negated(m.start()) else _planet_near(sent, m.start())
            if p and p in P and not P[p]["nb"]:
                flag(sent, f"{p} Neecha Bhanga", f"{p} has no Neecha Bhanga in this chart")
        if "navamsa" not in low and "d9" not in low and "d10" not in low and "varga" not in low:
            refs = [(int(m.group(1)), m) for m in ORD_RE.finditer(sent)]
            refs += [(THEME_HOUSE[(m.group(1) or m.group(2)).lower()], m) for m in THEME_RE.finditer(sent)
                     if not any(o.start() <= m.start() <= o.end() + 3 for _, o in refs)]
            for h, m in refs:
                p = None if negated(m.start()) else _planet_near(sent, m.start())
                if not p or p not in P:
                    continue
                back, ahead = low[max(0, m.start() - 16):m.start()], low[m.end():m.end() + 12]
                if re.search(r"\b(rul\w*|lord\w*|own\w*|govern\w*)\b", back) or re.match(r"[\s-]*(house\s+)?lord", ahead):
                    if h not in P[p]["owns"]:
                        flag(sent, f"{p} rules H{h}", f"{p} rules house(s) {sorted(P[p]['owns']) or 'none'}")
                elif re.search(r"aspect|drishti|glance", low[max(0, m.start() - 40):m.start()]):
                    if h not in P[p]["aspects"]:
                        flag(sent, f"{p} aspects H{h}", f"{p} aspects houses {sorted(P[p]['aspects'])}")
                elif re.search(r"\b(in|into|through|transit\w*|sits|placed|occup\w*|enter\w*)\b", back):
                    if h not in P[p]["houses"]:
                        flag(sent, f"{p} in H{h}", f"{p} is not in the {h}th house by any reckoning used")
        if "navamsa" not in low and "d9" not in low:
            for m in re.finditer(r"\b(?:in|into|transiting|through)\s+(" + "|".join(SIGNS) + r")\b", sent):
                p = None if negated(m.start()) else _planet_near(sent, m.start())
                if p and p in P and m.group(1) not in P[p]["sign"]:
                    flag(sent, f"{p} in {m.group(1)}", f"{p} is in {', '.join(sorted(P[p]['sign']))}")
        for m in re.finditer(r"\b(" + "|".join(SIGNS) + r")\s+(rising|ascendant|lagna)\b", sent):
            if m.group(1) != facts["lagna"]:
                flag(sent, f"{m.group(1)} rising", f"the lagna is {facts['lagna']}")
        for key, name in YOGAS.items():
            if key in low and not negated(low.index(key)) and name not in facts["yogas"]:
                flag(sent, name, f"{name} is not present in this chart")
        if "sade sati" in low and not negated(low.index("sade sati")) and not facts["sade_sati"] and re.search(r"\b(you are|you're|running|currently|now|in your)\b", low):
            flag(sent, "Sade Sati now", "Saturn is not in Sade Sati position from the Moon today")
        if re.search(r"\b(you are|you're|currently|right now|now running|running)\b", low):
            m = re.search(r"\b(" + "|".join(PLANETS) + r")\s+(maha\s?dasha|mahadasha|major period)", sent, re.I)
            if m and facts["maha"] and m.group(1).title() != facts["maha"]:
                flag(sent, f"{m.group(1)} mahadasha now", f"the running mahadasha is {facts['maha']}")
            m = re.search(r"\b(" + "|".join(PLANETS) + r")\s+(antar\s?dasha|antardasha|bhukti|sub-period)", sent, re.I)
            if m and facts["antar"] and m.group(1).title() != facts["antar"]:
                flag(sent, f"{m.group(1)} antardasha now", f"the running antardasha is {facts['antar']}")
        dates = [(m.group(0), (int(m.group(2)), MONTHS[m.group(1).lower()[:3]]), m.start()) for m in DATE_RE.finditer(sent)]
        for raw, ym, _ in dates:
            if not _in_life(ym, facts["months"]):
                flag(sent, raw, "this date falls outside the native's daśā span")
        period_checks(sent, facts, flag)
        if facts.get("kp"):
            verdict_checks(sent, facts, flag)
    return issues


MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
FULL_DATE = re.compile(r"\b(?:(\d{1,2})\s+)?" + MON + r"\s+(?:(\d{1,2}),\s+)?(\d{4})\b", re.I)
LEVEL = {"pratyantar": "praty", "sub-sub": "praty", "maha": "maha", "antar": "antar", "bhukti": "antar"}  # longest first
PERIOD = re.compile(r"\b(" + "|".join(PLANETS) + r")(?:\s*(?:[-–/]|\s+with\s+)\s*(" + "|".join(PLANETS) + r"))?\s+"
                    r"(maha\s?dasha|mahadasha|antar\s?dasha|antardasha|bhukti|pratyantar\w*|sub-sub)", re.I)


def _dates(sent: str) -> list[tuple[date, int, int, bool]]:
    """(date, start, end, day_known) for every 'Mon YYYY' / 'D Mon YYYY'; 'Jan to Jun 2028' borrows the year."""
    out = []
    for m in FULL_DATE.finditer(sent):
        day = m.group(1) or m.group(3)
        d = date(int(m.group(4)), MONTHS[m.group(2).lower()[:3]], int(day) if day and 0 < int(day) <= 28 else 15)
        out.append((d, m.start(), m.end(), bool(day)))
    for m in re.finditer(r"\b" + MON + r"\s*(?:to|–|-)\s*(?:\d{1,2}\s+)?" + MON + r"\s+(\d{4})\b", sent, re.I):
        if not any(s <= m.start() < e for _, s, e, _ in out):
            y, a, b = int(m.group(3)), MONTHS[m.group(1).lower()[:3]], MONTHS[m.group(2).lower()[:3]]
            out.append((date(y - (a > b), a, 15), m.start(), m.start() + len(m.group(1)), False))
    return sorted(out, key=lambda x: x[1])


def _overlap(s1: date, e1: date, s2: date, e2: date) -> int:
    return max(0, (min(e1, e2) - max(s1, s2)).days)


def period_checks(sent: str, facts: dict, flag) -> None:
    """Dates and windows tied to a named daśā period must match that period."""
    S, low, dates = facts["spans"], sent.lower(), _dates(sent)
    n = lambda d: d.year * 12 + d.month
    # 1) "Mercury antardasha until April 2029", "Now to June 2029: Mercury antardasha", "Ketu pratyantar from Nov 2026"
    mentions = list(PERIOD.finditer(sent))
    for d, ds, de, _ in dates:
        near = [m for m in mentions if min(abs(ds - m.end()), abs(m.start() - de)) <= 80]
        if not near:
            continue
        m = min(near, key=lambda m: min(abs(ds - m.end()), abs(m.start() - de)))
        a, b = m.group(1).title(), (m.group(2) or "").title()
        level = next(v for k, v in LEVEL.items() if k in m.group(3).lower().replace(" ", ""))
        lord, parent = (a, None) if level == "maha" else ((b, a) if b else (a, None))
        key = "maha" if level == "antar" else "antar"
        mine = [x for x in S[level] if x["lord"] == lord and (parent is None or x.get(key) == parent)]
        if not mine:
            flag(sent, f"{a}{'-' + b if b else ''} {m.group(3)}", f"there is no such {level} period in this chart")
            continue
        before, after = low[max(0, ds - 12):ds], low[de:de + 6]
        if re.search(r"(\bto|\buntil|\btill|\bthrough|\bends?|–|-)\s*$", before):
            ok, what = any(abs(n(d) - x["b"]) <= 1 for x in mine), "ends"
        elif re.search(r"\bfrom\s*$|\bstarts?\s*$|\bbegins?\s*$", before) or re.match(r"\s*(to\b|–|-)", after):
            ok, what = any(abs(n(d) - x["a"]) <= 1 for x in mine), "starts"
        else:
            ok, what = any(x["a"] - 1 <= n(d) <= x["b"] + 1 for x in mine), "runs"
        if not ok:
            when = "; ".join(f"{x['from']} to {x['to']}" for x in mine[:3])
            flag(sent, f"{lord} {m.group(3)} {d:%b %Y}", f"{(parent + '-') if parent else ''}{lord} {m.group(3)} runs {when}")
    # 2) timeline lines: "Nov 2026 to Jan 2027: Mercury with Venus — …" / "Until 16 Nov 2026: Mercury-Mercury."
    head, colon, rest = sent.partition(":")
    hd = [x for x in dates if x[1] < len(head)]
    if not colon or not hd:
        return
    if len(hd) >= 2:
        s, e = hd[0][0], hd[1][0]
    elif re.search(r"\b(now|until|till|through|today)\b", head.lower()):
        s, e = facts["today"], hd[0][0]
    else:
        return
    if e <= s:
        return
    label = re.split(r"—|–|\(|\.|,|;| - ", rest, maxsplit=1)[0]
    named = [ALIAS[x.lower()] for x in PLANET_RE.findall(label)]
    if not named:
        return
    total = (e - s).days
    if len(named) >= 2 or "pratyantar" in label.lower():
        claim, levels = named[-1], ["praty"]
    else:
        claim, levels = named[0], ["maha", "antar", "praty"]
    if len(named) > 2:
        return  # a sequence ("Sun, Moon and Mars") — each covers only part of the window by design
    covered = max(sum(_overlap(s, e, x["s"], x["e"]) for x in S[lv] if x["lord"] == claim) for lv in levels)
    if covered < total / 2:
        running = [f"{x['antar']}-{x['lord']} ({x['s']:%d %b %Y}–{x['e']:%d %b %Y})" for x in S["praty"]
                   if _overlap(s, e, x["s"], x["e"]) > 0][:4]
        flag(sent, f"{claim} period {s:%b %Y}–{e:%b %Y}",
             f"{claim} does not run for most of that window; the periods are " + ", ".join(running))


POSITIVE = re.compile(r"\b(strong|strongest|favourable|favorable|best|excellent|ideal|great time|good time|good window|"
                      r"peak|promising|supportive|golden)\b", re.I)
NEGATIVE = re.compile(r"\b(challenging|difficult|hard|tough|avoid|struggle|weak|worst|unfavourable|unfavorable|"
                      r"blocked|setback)\b", re.I)
TOPIC_WORDS = {"career": r"career|job|work|promotion|profession", "business": r"business|trade", "marriage": r"marri|wedding|spouse",
               "vehicle": r"vehicle|car\b", "exams": r"exam|interview", "job_change": r"change|switch|new job",
               "love": r"love|relationship", "money": r"money|income|wealth|financ|gains", "property": r"property|vehicle|house",
               "foreign": r"abroad|foreign|visa|settle", "children": r"child|baby", "education": r"exam|study|education",
               "health": r"health|recover", "litigation": r"court|case|dispute|legal"}


def verdict_checks(sent: str, facts: dict, flag) -> None:
    """A window called strong/good must not be one the KP engine rates challenging, and vice versa."""
    pos, neg = bool(POSITIVE.search(sent)), bool(NEGATIVE.search(sent))
    if pos == neg or NEG.search(sent):  # no judgement, both, or negated: leave it
        return
    topics = [t for t in facts["kp"] if re.search(TOPIC_WORDS.get(t, t), sent, re.I)] or \
             (list(facts["kp"]) if len(facts["kp"]) == 1 else [])
    dates = _dates(sent)
    if not topics or not dates:
        return
    if len(dates) >= 2:
        s, e = dates[0][0], dates[1][0]
    elif re.search(r"\b(now|until|till|through)\b", sent, re.I):
        s, e = facts["today"], dates[0][0]
    else:
        s = e = dates[0][0]
    if e < s:
        return
    for t in topics:
        if facts.get("kp_kind", {}).get(t) == "risk":
            continue  # "strong" means high risk there; wording checks would invert
        span = max((e - s).days, 1)
        cover = {}
        for w in facts["kp"][t]:
            o = _overlap(s, e, w["s"], w["e"]) if e > s else (1 if w["s"] <= s < w["e"] else 0)
            if o:
                cover[w["verdict"]] = cover.get(w["verdict"], 0) + o
        if not cover:
            continue
        main = max(cover, key=cover.get)
        if cover[main] < span / 2 and e > s:
            continue
        if (pos and main == "challenging") or (neg and main == "strong"):
            rated = ", ".join(f"{w['label']} {w['s']:%b %Y}–{w['e']:%b %Y}: {w['verdict']}" for w in facts["kp"][t]
                              if (_overlap(s, e, w["s"], w["e"]) if e > s else w["s"] <= s < w["e"]))
            flag(sent, f"{t} window {s:%b %Y}–{e:%b %Y} called {'good' if pos else 'difficult'}",
                 f"the KP engine rates it {main} ({rated})")


def correction_note(issues: list[dict]) -> str:
    lines = "\n".join(f"- You wrote \"{i['claim']}\" but {i['truth']}." for i in issues)
    return ("Your draft contradicts the computed chart data:\n" + lines +
            "\nRewrite the whole answer, fixing only these points and keeping everything else. Do not add any new "
            "astrological facts, dates or yogas that are not in the chart data.")


def strip(text: str, issues: list[dict]) -> str:
    """Last resort: drop the sentences that still contradict the chart."""
    bad = {i["sentence"] for i in issues}
    out = text
    for s in bad:
        out = out.replace(s, "")
    out = re.sub(r"\n\s*[-*•]\s*\n", "\n", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()
