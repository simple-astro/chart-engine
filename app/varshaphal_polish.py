"""AI-polished wording for the Varshaphal reading, to compare with the rules (app/varshaphal.py).

The rules decide every tone and fact; the AI only rewrites the sentences warmer and smoother, in one call that
returns JSON. A fact guard then checks each rewritten line: it may name no planet, sign, house, yoga, Saham, month or
year that the rules' own line (and its reason) did not, and it may not use certainty or death wording. A line that
fails keeps the rules' wording and is listed in "kept", so the comparison shows where the AI tried to add something.
Results are cached per chart, year and rules text, so switching back and forth costs one call.
"""
from __future__ import annotations

import hashlib
import json
import re

from core import constants as C

MODEL = "claude-haiku-4-5"
_CACHE: dict[str, dict] = {}
_CACHE_MAX = 300

SYSTEM = (
    "You polish the wording of a Varshaphal (Tajika annual chart) reading for a warm, modern Vedic astrology app. "
    "You receive JSON lines already decided by rules. Rewrite each line so it reads naturally and kindly, in plain "
    "English for someone who is not an astrologer, keeping its meaning and its strength exactly (a 'go' line stays "
    "encouraging, a 'care' line stays careful). Rules: do not add any astrological fact: no planet, sign, house number, "
    "yoga, Saham, date, month or year that the line does not already contain; keep every one that it does contain only "
    "if it helps. Tendencies, never certainties ('tends to', 'looks supportive'; never 'will definitely', 'guaranteed'). "
    "No fear or doom words, nothing about death or lifespan, no medical, legal or financial advice. Each line at most "
    "30 words; the headline at most 35. Reply with JSON only, each value a plain string (just the rewritten line, "
    "not the tone or reason): "
    '{"headline": "...", "areas": {"<key>": "..."}, "dasha": "...", "months": ["...", ...]} '
    "with exactly as many months as given, in the same order.")

PLANETS = [p for p in C.VIMSOTTARI_ORDER]
_WORDS = re.compile(r"\b(" + "|".join(PLANETS + C.SIGNS + [
    "Ithasala", "Ishrafa", "Radda", "Nakta", "Yamaya", "Kamboola", "Ikkabala", "Induvara", "Muntha", "Saham",
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
    "December", "Lagna"]) + r")\b|\b(\d{1,2}(?:st|nd|rd|th))\b|\b(\d{4})\b", re.I)
_BAD = re.compile(r"\b(definitely|guarantee\w*|certainly will|for sure|death|die|dying|lifespan|longevity|fatal|"
                  r"doom\w*|disaster)\b", re.I)


def _facts(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORDS.finditer(text or "")}


def guard(new: str, source: str) -> str | None:
    """The reason a rewritten line is refused, or None if it is fine."""
    if not isinstance(new, str) or not new.strip():
        return "empty"
    if len(new.split()) > 45:
        return "too long"
    extra = _facts(new) - _facts(source)
    if extra:
        return "added " + ", ".join(sorted(extra))
    if _BAD.search(new):
        return "certainty or fear wording"
    return None


def _payload(reading: dict) -> dict:
    return {"headline": reading["headline"],
            "areas": {a["key"]: {"tone": a["tone"], "line": a["text"], "reason": a["why"]} for a in reading["areas"]},
            "dasha": {"verdict": (reading.get("dasha") or {}).get("verdict"), "line": (reading.get("dasha") or {}).get("text", "")},
            "months": [{"planet": m["lord"], "tone": m["tone"], "line": m["text"]} for m in reading["months"]]}


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        out = json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def polish(reading: dict, key: str, model: str | None = None) -> tuple[dict, dict | None]:
    """(polished lines with "kept" reasons, token usage or None when served from the cache). Raises if the AI is
    unavailable."""
    from app import chat
    payload = _payload(reading)
    ck = hashlib.sha1((key + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
    if ck in _CACHE:
        return _CACHE[ck], None
    model = model or MODEL
    resp = chat._client().messages.create(model=model, max_tokens=1400, system=SYSTEM,
                                          messages=[{"role": "user", "content": json.dumps(payload)}])
    u = getattr(resp, "usage", None)
    use = {"model": model, "input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
           "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
           "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
    raw = _parse("".join(getattr(b, "text", "") for b in resp.content))
    kept: list[dict] = []

    def take(field: str, new, src_line: str, src_all: str) -> str:
        if isinstance(new, dict):  # the model sometimes echoes the input shape: {"tone", "line", "reason"}
            new = new.get("line") or new.get("text")
        why = guard(new, src_all)
        if why:
            kept.append({"field": field, "why": why, "tried": new if isinstance(new, str) else ""})
            return src_line
        return new.strip()

    areas_in = raw.get("areas") if isinstance(raw.get("areas"), dict) else {}
    months_in = raw.get("months") if isinstance(raw.get("months"), list) else []
    d = reading.get("dasha") or {}
    out = {
        "headline": take("headline", raw.get("headline"), reading["headline"],
                         reading["headline"] + " " + " ".join(a["why"] for a in reading["areas"])),
        "areas": {a["key"]: take(a["label"], areas_in.get(a["key"]), a["text"], a["text"] + " " + a["why"])
                  for a in reading["areas"]},
        "dasha": take("Dasha", raw.get("dasha"), d.get("text", ""), d.get("text", "")) if d.get("text") else "",
        "months": [take(f"{m['lord']} period", months_in[i] if i < len(months_in) else None, m["text"],
                        m["text"] + " " + m["lord"]) for i, m in enumerate(reading["months"])],
        "kept": kept, "model": model,
    }
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[ck] = out
    return out, use
