"""Transits read the Nadi / KP way, and whether they trigger an event that the chart and dasha already allow.

A transiting planet gives the results of its nakshatra (star) lord — *what* — and its sub lord decides
*whether* — both read through the houses those lords signify in the natal chart (occupied and owned, Rahu/Ketu
as agents). The house it transits in the Bhava Chalit is *where* it acts; its own natal houses are shown for
reference only.

An event needs the natal promise (the topic's cusp sub lord) and a dasha window that supports it (Dasa ->
Bhukti -> Antar, from core.kp_predict); that pair is what the status rests on, because it is what our backtest
supports (14/17 of the book's dated events fell in favourable windows). Transits are shown as hints only. The
classical KP trigger — a slow planet transiting a sign, star and sub all ruled by the running dasha lords, its sub
lord supporting the matter — fired near none of the book's 15 dated events (base rate ~8% of days), and a softer
"slow planet in a dasha lord's star or sub" rule fired as often on random days as on event days (lift x1.0).
Taneja: a retrograde or stationary transiting planet "carries no meaning", so Jupiter and Saturn are ignored then.
"""
from __future__ import annotations

from datetime import date, timedelta

from core import kp_predict as K
from core.constants import SIGN_LORDS

TOPICS = ["marriage", "career", "job_change", "business", "money", "property", "foreign", "children"]
SHORT = {"marriage": "Marriage", "career": "Job & promotion", "job_change": "Job change", "business": "Business",
         "money": "Money", "property": "Property", "foreign": "Abroad", "children": "Children"}
SLOW = ("Jupiter", "Saturn", "Rahu", "Ketu")
# Taneja: "if any of the transiting planets is stationary or retrograde it carries no meaning". Rahu and Ketu move
# backwards by nature and are exempt. Stationary = under a tenth of the planet's mean daily motion.
MEAN_SPEED = {"Jupiter": 0.083, "Saturn": 0.034}


def inert(r: dict) -> bool:
    """A transiting Jupiter or Saturn that is retrograde or stationary carries no trigger value."""
    return r["planet"] in MEAN_SPEED and (r["retrograde"] or abs(r.get("speed", 1.0)) < 0.1 * MEAN_SPEED[r["planet"]])


def strict_triggers(table: list[dict], dasha_lords: set[str], topic: str, skip_inert: bool = True) -> list[dict]:
    """Slow planets moving in a sign, star and sub all ruled by the running dasha lords, whose sub lord supports
    the matter (the classical KP rule, made specific to the matter by the sub lord)."""
    return [{"planet": r["planet"], "why": f"in a sign, star and sub ruled by your dasha lords "
             f"({r['sign_lord']} / {r['star_lord']} / {r['sub_lord']})"}
            for r in table if r["planet"] in SLOW and not (skip_inert and inert(r))
            and r["topics"][topic] == "supports" and {r["sign_lord"], r["star_lord"], r["sub_lord"]} <= dasha_lords]
DASHA_OK = ("strong", "favourable")


def transit_verdict(houses_star: set[int], houses_sub: set[int], good: set[int], bad: set[int]) -> str:
    """The sub lord decides; the star lord must point at the topic too for full support."""
    sub_for, sub_against = houses_sub & good, houses_sub & bad
    if sub_for and len(sub_for) > len(sub_against) and houses_star & good:
        return "supports"
    if sub_against and not sub_for:
        return "against"
    return "mixed" if sub_for or houses_star & good else "neutral"


def rows(chart: dict, planets: list[dict], topics: list[str] = TOPICS) -> list[dict]:
    """The significator table: each transiting planet at planet / star / sub level, with a verdict per topic."""
    hs = lambda p: sorted(K.own_houses(chart, p))
    out = []
    for r in planets:
        star, sub = r["star_lord"], r["sub_lord"]
        h_star, h_sub = set(hs(star)), set(hs(sub))
        out.append({"planet": r["planet"], "house": r["h_bhava"], "retrograde": r["retrograde"],
                    "speed": r.get("speed"), "inert": inert(r),
                    "sign_lord": SIGN_LORDS[r["sign_index"]], "planet_houses": hs(r["planet"]), "star_lord": star, "star_houses": sorted(h_star),
                    "sub_lord": sub, "sub_houses": sorted(h_sub),
                    "topics": {t: transit_verdict(h_star, h_sub, K.TOPICS[t][2], K.TOPICS[t][3]) for t in topics}})
    return out


def _fmt(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %-d, %Y")


def ladder(chart: dict, day: date, table: list[dict], dasha: list[dict]) -> list[dict]:
    """Promise -> Dasha -> Trigger for each topic on ``day``."""
    lords = {d["lord"]: d["level"] for d in dasha}
    out = []
    for t in TOPICS:
        title, _, good, bad, *_ = K.TOPICS[t]
        pr = K.promise(chart, t)
        pred = K.predict(chart, t, start=day, months=24)
        win = pred["windows"][0] if pred["windows"] else None
        nxt = next((w for w in pred["windows"][1:] if w["verdict"] in DASHA_OK), None)
        sig = set(K.significators(chart, t))
        promised = pr["verdict"] != "not clearly promised"
        dasha_ok = bool(win and win["verdict"] in DASHA_OK)

        def links(r: dict) -> list[str]:
            # The star or sub lord must itself signify this matter (a significator, or a dasha lord that supports
            # it), and the transit's own sub lord must lean towards it. A planet in its own star links to nothing.
            if r["topics"][t] not in ("supports", "mixed") or r["inert"]:
                return []
            why = []
            for lvl, q in (("star", r["star_lord"]), ("sub", r["sub_lord"])):
                if q == r["planet"] or q not in sig:
                    continue
                why.append(f"in the {lvl} of {q}, your {K_LEVEL[lords[q]]} lord" if q in lords
                           else f"in the {lvl} of {q}, a significator of {SHORT[t].lower()}")
            return why

        dl = set(lords)
        triggers = strict_triggers(table, dl, t)
        resting = [r["planet"] for r in table if r["inert"] and r["topics"][t] == "supports"
                   and {r["sign_lord"], r["star_lord"], r["sub_lord"]} <= dl]
        supporting = [{"planet": r["planet"], "why": w} for r in table if r["planet"] in SLOW
                      and r["planet"] not in {x["planet"] for x in triggers} for w in links(r)[:1]]
        sun = next((r for r in table if r["planet"] == "Sun"), None)
        month = bool(sun and sun["topics"][t] == "supports" and {sun["sign_lord"], sun["star_lord"]} <= dl)
        if not promised:
            status, label = "not_promised", "Not clearly promised"
        elif not dasha_ok:
            status, label = "not_now", "Not now"
        elif win["verdict"] == "strong":
            status, label = "strong", "Strong window"
        else:
            status, label = "open", "Window open"
        out.append({
            "topic": t, "title": SHORT[t], "full_title": title, "houses_for": sorted(good), "houses_against": sorted(bad),
            "status": status, "label": label,
            "promise": {"ok": promised, "verdict": pr["verdict"], "cusp": pr["cusp"], "sub_lord": pr["cusp_sub_lord"],
                        "signifies": pr["signifies"]},
            "dasha": {"ok": dasha_ok, "verdict": win["verdict"] if win else None,
                      "lords": f"{win['maha']}–{win['antar']}–{win['praty']}" if win else None,
                      "until": win["ends"] if win else None},
            "trigger": {"ok": bool(triggers), "planets": triggers, "supporting": supporting, "sun": month,
                        "resting": resting},
            "next_window": {"starts": nxt["starts"], "ends": nxt["ends"], "lords": f"{nxt['maha']}–{nxt['antar']}–{nxt['praty']}"}
            if nxt and not (dasha_ok and promised) else None,
            "summary": _summary(status, t, win, nxt),
            "nature": nature(chart, t, win) if status in ("strong", "open") else [],
        })
    order = {"strong": 0, "open": 1, "not_now": 2, "not_promised": 3}
    return sorted(out, key=lambda x: order[x["status"]])


K_LEVEL = {"maha": "Mahadasha", "antar": "Antardasha", "praty": "Pratyantar"}


def _summary(status: str, t: str, win: dict | None, nxt: dict | None) -> str:
    name = SHORT[t].lower()
    if status == "not_promised":
        return f"The chart does not clearly promise {name}; timing matters less than effort here."
    if status == "not_now":
        return (f"The running dasha does not support {name}. The next supportive window is "
                f"{_fmt(nxt['starts'])} – {_fmt(nxt['ends'])}." if nxt
                else f"The running dasha does not support {name} in the next two years.")
    return (f"The chart promises {name} and the running dasha {'strongly ' if status == 'strong' else ''}"
            f"supports it until {_fmt(win['ends'])}.")


# The kind of work a period lord's natural significations point to (traditional karakatwa).
WORK = {"Sun": "government, authority or administration", "Moon": "public dealing, care, food or travel",
        "Mars": "engineering, property, police, army or surgery", "Mercury": "business, communication, accounts or IT",
        "Jupiter": "teaching, finance, law or advice", "Venus": "arts, design, fashion, hospitality or luxury goods",
        "Saturn": "service, technical, labour-intensive or long-term work", "Rahu": "technology, foreign links or "
        "unconventional fields", "Ketu": "research, healing, spiritual or highly technical detail work"}


def nature(chart: dict, t: str, win: dict) -> list[str]:
    """What kind of event the running dasha points to, from the houses its lords signify (Nadi interpretation)."""
    hs: set[int] = set()
    for lvl in ("maha", "antar", "praty"):
        hs |= K.fourfold(chart, win[lvl])
    out = []
    if t == "marriage":
        if 5 in hs:
            out.append("The dasha lords also signify the 5th — this leans towards a love marriage.")
        if 11 not in hs:
            out.append("The 11th is not signified, so finalising may take longer than expected.")
        if 2 not in hs:
            out.append("The 2nd is not signified — a relationship may form before it turns into marriage.")
    if t in ("career", "job_change", "business"):
        lord = win["antar"] if win["antar"] not in ("Rahu", "Ketu") or win["maha"] in ("Rahu", "Ketu") else win["maha"]
        out.append(f"The {lord} period points to work in {WORK[lord]}.")
        if {1, 6, 10} <= hs:
            out.append("1, 6 and 10 together favour leadership, politics or public roles.")
        elif {6, 10} <= hs:
            out.append("6 and 10 together favour management and service roles.")
    if t == "property" and 6 in hs:
        out.append("The 6th is involved — a loan is likely to be part of the purchase.")
    if t == "foreign" and 12 in hs and 9 in hs:
        out.append("Both the 9th and 12th are signified — long-distance travel, possibly settling abroad.")
    return out


def events(profile: dict, day: date, overlay: dict) -> dict:
    chart = profile["chart"]
    table = rows(chart, overlay["planets"])
    return {"date": day.isoformat(), "topics": TOPICS, "titles": SHORT, "rows": table,
            "ladder": ladder(chart, day, table, overlay["dasha"])}
