"""Answer questions about a saved chart: direct lookups first, Claude for the rest."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
       "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}
DEFAULT_MODEL = "claude-sonnet-5-5"


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


def _llm_context(profile: dict) -> str:
    chart = profile["chart"]
    md, ad = current_dasha(chart)
    slim_dasha = [{"lord": d["lord"], "start": d["start"][:10], "end": d["end"][:10],
                   "antardashas": [{"lord": c["lord"], "start": c["start"][:10], "end": c["end"][:10]}
                                   for c in d.get("children", [])]} for d in chart["dasha"]]
    data = {
        "birth": profile["request"], "meta": chart["meta"], "lagna": chart["lagna"],
        "grahas": chart["grahas"], "houses": chart["houses"], "significators": chart["significators"],
        "navamsa_D9": chart["vargas"].get("D9"), "dasha": slim_dasha,
        "current_mahadasha": md and md["lord"], "current_antardasha": ad and ad["lord"],
        "today": datetime.now(timezone.utc).date().isoformat(),
    }
    return json.dumps(data, separators=(",", ":"))


SYSTEM = (
    "You are a Vedic astrology (Jyotish, KP-aware) assistant. Answer the user's question using ONLY "
    "the birth chart data below; cite the specific placements, lords, KP significators and dasha "
    "periods you rely on. Be concrete but honest: astrology is interpretive, so frame timing and "
    "outcomes as tendencies, never certainties, and do not give medical, legal or financial advice. "
    "If the data cannot answer the question, say so. Keep answers concise.\n\nCHART DATA (JSON):\n"
)


def ask_llm(profile: dict, question: str, history: list[dict]) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set on the server, so open-ended questions are unavailable. "
                           "Data lookups (e.g. 'where is my Moon?', 'current dasha') still work.")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("The 'anthropic' package is not installed (pip install -e '.[llm]').") from exc
    client = anthropic.Anthropic(api_key=key)
    msgs = [{"role": h["role"], "content": h["content"]} for h in history[-6:]
            if h.get("role") in ("user", "assistant") and h.get("content")]
    msgs.append({"role": "user", "content": question})
    resp = client.messages.create(
        model=os.environ.get("CHART_LLM_MODEL", DEFAULT_MODEL), max_tokens=1024,
        system=SYSTEM + _llm_context(profile), messages=msgs,
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
