"""The critic: a second, small AI read of a draft answer, for what rules cannot catch.

The fact check (app/factcheck.py) already verifies chart claims and catches stock phrases. The critic covers the house
rules that need judgement: fear or doom wording, false certainty, medical, legal or financial advice, any talk of death
or longevity, an answer that dodges the question, and a draft that contradicts itself. These are the same things the
astrologers tick in Studio Review, run live before the person sees the answer.

It runs only where a slip costs most (marriage, health, children, money, family, mood, business, or words about
death, illness or court), or on every answer, or never: the admin chooses (config "critic"). One small call; if it
finds problems the draft is rewritten once through the same correction pass the fact check uses, and that rewrite is
kept only if it still agrees with the chart. It never blocks an answer: any failure leaves the draft as it was.
"""
from __future__ import annotations

import json
import re

from app.teach import topics_of

MODEL = "claude-haiku-4-5"
MODES = ("off", "auto", "always")
STAKES = {"Marriage & love", "Health", "Children", "Money", "Family", "Mind & mood", "Business"}
_SEVERE = re.compile(r"\b(die|dying|death|dead|how long will i live|lifespan|longevity|suicid\w*|cancer|miscarriage|"
                     r"divorce|bankrupt\w*|lawsuit|court|surgery|loan|invest\w*|stocks?)\b", re.I)

TYPES = {
    "fear": "Remove the fear or doom wording; say it as a tendency, with something the person can do.",
    "certainty": "Replace the certainties (\"will definitely\", \"for sure\", \"guaranteed\") with tendencies "
                 "(\"tends to\", \"looks supportive\").",
    "advice": "Do not give medical, legal or financial advice; say what the chart shows as a tendency and suggest a "
              "doctor, lawyer or adviser for the decision itself.",
    "death": "Remove every statement about death, longevity or fatal accidents.",
    "generic": "Replace generic wording with the actual chart reason from the data.",
    "off_question": "Answer what they actually asked first, in the opening lines.",
    "inconsistent": "Fix the contradiction inside the answer so that it says one thing.",
    "tone": "Be warmer and calmer; this person may be anxious, so acknowledge it briefly and stay practical.",
}

SYSTEM = (
    "You review a draft answer from an AI Vedic astrologer (KP and Nadi methods) before the client sees it. House "
    "rules: warm, calm and never judgmental; tendencies, never certainties; no fear or doom wording; no medical, legal "
    "or financial advice (suggest a professional for the decision); no statements about death or longevity; practical "
    "habits first; high-stakes decisions are suggested for review with the founding astrologer. Also check that the "
    "answer addresses the question asked, is not generic filler, and does not contradict itself. Do not judge the "
    "astrology itself: a separate check already verifies the chart facts. Quote the offending words in each problem. "
    "Be strict but fair: if the draft is fine, say so. Reply with JSON only: "
    '{"verdict": "ok" or "revise", "problems": [{"type": "fear|certainty|advice|death|generic|off_question|'
    'inconsistent|tone", "detail": "<the words and what is wrong, one short line>"}]} with at most 4 problems.')


def stakes(message: str) -> str | None:
    hit = [t for t in topics_of(message) if t in STAKES]
    if hit:
        return hit[0]
    return "sensitive words" if _SEVERE.search(message or "") else None


def wanted(mode: str, message: str) -> str | None:
    """Why the critic should read this answer, or None."""
    if mode == "always":
        return "every answer"
    if mode == "auto":
        return stakes(message)
    return None


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        out = json.loads(m.group(0))
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def review(question: str, draft: str, model: str = MODEL) -> tuple[dict, dict]:
    """({"verdict", "problems"}, token usage) from the critic. Raises if the AI is unavailable."""
    from app import chat
    resp = chat._client().messages.create(
        model=model, max_tokens=300, system=SYSTEM,
        messages=[{"role": "user", "content": f"QUESTION:\n{question[:800]}\n\nDRAFT ANSWER:\n{draft[:3500]}"}])
    u = getattr(resp, "usage", None)
    use = {"input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
           "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
           "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
    raw = _parse("".join(getattr(b, "text", "") for b in resp.content))
    problems = [{"type": p["type"], "detail": str(p.get("detail") or "")[:240]}
                for p in (raw.get("problems") if isinstance(raw.get("problems"), list) else [])[:4]
                if isinstance(p, dict) and p.get("type") in TYPES]
    return {"verdict": "revise" if raw.get("verdict") == "revise" and problems else "ok", "problems": problems}, use


def note(problems: list[dict], words: int | None = None) -> str:
    lines = "\n".join(f"- {TYPES[p['type']]}" + (f" ({p['detail']})" if p["detail"] else "") for p in problems)
    limit = f"Stay within {words} words in total. " if words else ""
    return ("A reviewer read your draft and asked for these changes:\n" + lines + "\nRewrite the whole answer, fixing "
            "only these points and keeping everything else. Do not add any new astrological facts, dates or yogas that "
            "are not in the chart data. Start directly with the corrected answer: no apology and no 'here is the "
            "corrected answer'. Keep every section, including the Do and Don't lists. " + limit +
            "If it runs long, shorten the explanation, never the Do and Don't lists.")
