"""Answer questions about a saved chart: direct lookups first, Claude for the rest."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from core.ashtakavarga import ashtakavarga
from core.dignity import dignity
from core.parivartana import exchanges

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
       "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}


def _dms(d: float) -> str:
    return f"{int(d)}°{int((d - int(d)) * 60):02d}′"


def _fmt_date(s: str) -> str:
    return datetime.fromisoformat(s).strftime("%d %b %Y")


def current_dasha(chart: dict, now: datetime | None = None) -> tuple[dict | None, dict | None]:
    now = now or datetime.now(timezone.utc)
    def active(d):
        return datetime.fromisoformat(d["start"]) <= now < datetime.fromisoformat(d["end"])
    md = next((d for d in chart["dasha"] if active(d)), None)
    ad = next((d for d in (md or {}).get("children", []) if active(d)), None)
    return md, ad


def _planet_line(chart: dict, name: str) -> str:
    g = chart["grahas"][name]
    k = g["kp"]
    extra = ", ".join(x for x, f in (("retrograde", g["retrograde"]), ("combust", g["combust"])) if f)
    return (f"{name}: {g['sign']} {_dms(g['degrees_in_sign'])}, {g['nakshatra']} pada {g['pada']}, "
            f"house {g['house']}. KP: sign lord {k['sign_lord']}, star lord {k['star_lord']}, "
            f"sub lord {k['sub_lord']}." + (f" ({extra})" if extra else ""))


def lookup(chart: dict, q: str) -> str | None:
    """Return an answer for simple data questions, or None to defer to the LLM."""
    t = q.lower()
    # Opinion/prediction questions go to the LLM even if they mention a planet.
    if re.search(r"\b(should|will|when|why|how|good|bad|predict|future|best|luck|career|marriage|health|"
                 r"money|wealth|remed|advice|mean|interpret)", t):
        return None

    if re.search(r"\b(all planets|planets|summary|overview|chart)\b", t) and not any(p.lower() in t for p in GRAHAS):
        return "\n".join(_planet_line(chart, p) for p in GRAHAS)

    if re.search(r"\b(lagna|ascendant|rising)\b", t):
        l = chart["lagna"]
        return (f"Lagna: {l['sign']} {_dms(l['ascendant'] % 30)}. KP: star lord "
                f"{l['kp']['star_lord']}, sub lord {l['kp']['sub_lord']}.")

    if "dasha" in t or "dasa" in t or "period" in t:
        md, ad = current_dasha(chart)
        if re.search(r"\b(all|list|full|every|timeline)\b", t):
            return "\n".join(f"{d['lord']}: {_fmt_date(d['start'])} – {_fmt_date(d['end'])}" for d in chart["dasha"])
        if not md:
            return "No active dasha period found for today's date."
        s = f"Mahadasha {md['lord']} ({_fmt_date(md['start'])} – {_fmt_date(md['end'])})"
        return s + (f", antardasha {ad['lord']} ({_fmt_date(ad['start'])} – {_fmt_date(ad['end'])})." if ad else ".")

    m = re.search(r"\bhouse\s*(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)\s+(?:house|cusp)\b|\b(" + "|".join(ORD) + r")\s+(?:house|cusp)\b", t)
    if m:
        n = int(m.group(1) or m.group(2) or ORD[m.group(3)])
        if 1 <= n <= 12:
            h = chart["houses"][n - 1]
            inside = [p for p in GRAHAS if chart["grahas"][p]["house"] == n]
            k = h["kp"]
            return (f"House {n}: {h['sign']} {_dms(h['degrees_in_sign'])}, lord {h['sign_lord']} "
                    f"(in house {chart['grahas'][h['sign_lord']]['house']}). KP: star lord {k['star_lord']}, "
                    f"sub lord {k['sub_lord']}. Planets in house: {', '.join(inside) or 'none'}.")

    named = [p for p in GRAHAS if re.search(rf"\b{p.lower()}\b", t)]
    if named and re.search(r"\b(where|position|placed|placement|sign|house|nakshatra|star|sub|degree|show|what)\b", t):
        return "\n".join(_planet_line(chart, p) for p in named)
    return None


def llm_context(profile: dict) -> str:
    chart = profile["chart"]
    md, ad = current_dasha(chart)
    slim_dasha = [{"lord": d["lord"], "start": d["start"][:10], "end": d["end"][:10],
                   "antardashas": [{"lord": c["lord"], "start": c["start"][:10], "end": c["end"][:10]}
                                   for c in d.get("children", [])]} for d in chart["dasha"]]
    signs = {p: g["sign_index"] for p, g in chart["grahas"].items()}
    lagna = chart["lagna"]["sign_index"]
    grahas = {p: {**g, "dignity": dignity(p, g["sign_index"])} for p, g in chart["grahas"].items()}
    akv = ashtakavarga(signs, lagna)
    data = {
        "birth": profile["request"], "meta": chart["meta"], "lagna": chart["lagna"],
        "grahas": grahas, "houses": chart["houses"], "significators": chart["significators"],
        "ashtakavarga": {"sav_by_house": [akv["sav"][(lagna + h) % 12] for h in range(12)],
                         "planet_bindus_in_own_sign": akv["own_bindus"]},
        "lord_exchanges_D1": exchanges(signs, lagna),
        "navamsa_D9": chart["vargas"].get("D9"), "dasha": slim_dasha,
        "current_mahadasha": md and md["lord"], "current_antardasha": ad and ad["lord"],
        "today": datetime.now(timezone.utc).date().isoformat(),
    }
    return json.dumps(data, separators=(",", ":"))
