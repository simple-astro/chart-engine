"""Chat assistant over a saved chart: Claude with tools for live transits, panchang and detail lookups."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone

from app import ask, storage
from app.schemas import PanchangRequest, TransitRequest, TransitScanRequest

DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # cheap + fast; override with CHART_LLM_MODEL
MAX_TOOL_ROUNDS = 6
MAX_WORDS = 300
HISTORY_LIMIT = 6
# Output budget per model call (300-word answers need ~500 tokens; the rest is headroom, no extended thinking).
MAX_TOKENS = 1500

SYSTEM = (
    "You are a friendly, knowledgeable Vedic astrology (Jyotish, KP-aware) assistant chatting with the "
    "owner of the birth chart below. Answer ANY question they ask about their chart: personality, "
    "career, marriage, health tendencies, finances, education, dasha timing, transits, divisional "
    "charts, panchang, remedies, or how astrological concepts work. Ground every answer in the chart "
    "data and name the placements, lords, KP significators and dasha periods you rely on. For "
    "questions about the present or future, call the tools (transits, transit events, panchang, "
    "dasha detail, divisional charts) instead of guessing positions.\n"
    "Length: HARD LIMIT of 300 words per reply, counting headings and bullets (aim for 120-180; never exceed 220). Lead with the direct answer, then the 3-5 most "
    "relevant placements; skip exhaustive lists, and offer to go deeper on one point instead of covering everything.\n"
    "Style: conversational, clear short bullets when helpful. Frame outcomes as "
    "tendencies, never certainties; do not give medical, legal or financial advice, and gently "
    "suggest a professional where appropriate. If the question is unrelated to astrology or the "
    "chart, politely steer back. Today's date is given in the data.\n\nCHART DATA (JSON):\n"
)

TOOLS = [
    {"name": "get_transits",
     "description": "Sidereal planet positions at a moment (default now), with each planet's house counted "
                    "from the native's lagna and from natal Moon (gochar).",
     "input_schema": {"type": "object", "properties": {
         "when": {"type": "string", "description": "ISO-8601 datetime, UTC if no offset. Omit for now."}}}},
    {"name": "get_transit_events",
     "description": "Upcoming sign ingresses, retrogrades/directs, and eclipses within a window.",
     "input_schema": {"type": "object", "properties": {
         "start": {"type": "string", "description": "ISO-8601 start; omit for now."},
         "days": {"type": "integer", "description": "1-31, default 30"}}}},
    {"name": "get_panchang",
     "description": "Panchang (tithi, nakshatra, yoga, karana, sunrise/sunset, Rahu kalam) for a date at the "
                    "birth location.",
     "input_schema": {"type": "object", "properties": {
         "date": {"type": "string", "description": "YYYY-MM-DD; omit for today"}}}},
    {"name": "get_divisional_chart",
     "description": "Planet signs in a divisional chart such as D9 (navamsa), D10 (dasamsa), D7, D60.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "e.g. D10"}},
                      "required": ["name"]}},
    {"name": "get_dasha_detail",
     "description": "Antardasha/pratyantar periods inside one mahadasha.",
     "input_schema": {"type": "object", "properties": {
         "mahadasha": {"type": "string", "description": "Planet name, e.g. Rahu"}}, "required": ["mahadasha"]}},
]


def _utc(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def run_tool(profile: dict, name: str, args: dict) -> dict:
    from app import routes  # local import: routes imports heavy engine modules
    chart, req = profile["chart"], profile["request"]
    ayan, node = chart["meta"]["ayanamsha"], chart["meta"]["node_type"]
    if name == "get_transits":
        r = routes.transits(TransitRequest(when=_utc(args.get("when")), ayanamsha=ayan, node_type=node))
        lagna, moon = chart["lagna"]["sign_index"], chart["grahas"]["Moon"]["sign_index"]
        for g in r["grahas"].values():
            g["house_from_lagna"] = (g["sign_index"] - lagna) % 12 + 1
            g["house_from_moon"] = (g["sign_index"] - moon) % 12 + 1
        return r
    if name == "get_transit_events":
        days = max(1, min(31, int(args.get("days") or 30)))
        return routes.transit_scan(TransitScanRequest(start=_utc(args.get("start")), days=days,
                                                      ayanamsha=ayan, node_type=node))
    if name == "get_panchang":
        d = date.fromisoformat(args["date"]) if args.get("date") else date.today()
        return routes.panchang(PanchangRequest(on=d, lat=req["lat"], lon=req["lon"], tz_name=req["tz_name"]))
    if name == "get_divisional_chart":
        key = str(args.get("name", "")).upper()
        if key not in chart["vargas"]:
            return {"error": f"Unknown chart. Available: {', '.join(chart['vargas'])}"}
        return {key: chart["vargas"][key]}
    if name == "get_dasha_detail":
        md = next((d for d in chart["dasha"] if d["lord"].lower() == str(args.get("mahadasha", "")).lower()), None)
        return md or {"error": "No such mahadasha in this chart"}
    return {"error": f"Unknown tool {name}"}


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set on the server. Add it to .env and restart.")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("The 'anthropic' package is not installed (pip install -e '.[llm]').") from exc
    return anthropic.Anthropic(api_key=key)


STATUS = {
    "get_transits": "Checking current transits…",
    "get_transit_events": "Scanning upcoming planetary events…",
    "get_panchang": "Looking up the panchang…",
    "get_divisional_chart": "Reading the divisional chart…",
    "get_dasha_detail": "Reading the dasha periods…",
}


def events(profile: dict, history: list[dict], message: str):
    """Run one chat turn, yielding {"type": "status"|"delta", "text": ...} as it progresses."""
    client = _client()
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_LIMIT:]]
    msgs.append({"role": "user", "content": message})
    system = [{"type": "text", "text": SYSTEM + ask.llm_context(profile),
               "cache_control": {"type": "ephemeral"}}]
    model = os.environ.get("CHART_LLM_MODEL", DEFAULT_MODEL)
    wrote = False
    for _ in range(MAX_TOOL_ROUNDS):
        with client.messages.stream(model=model, max_tokens=MAX_TOKENS, system=system, tools=TOOLS,
                                    messages=msgs) as stream:
            for text in stream.text_stream:
                yield {"type": "delta", "text": text}
                wrote = wrote or bool(text.strip())
            resp = stream.get_final_message()
        u = getattr(resp, "usage", None)
        yield {"type": "usage", "model": model, "round": 1,
               "input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
               "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
               "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        if resp.stop_reason != "tool_use":
            return
        if wrote:
            yield {"type": "delta", "text": "\n\n"}
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                yield {"type": "status", "text": STATUS.get(b.name, "Looking that up…")}
                try:
                    out = run_tool(profile, b.name, b.input or {})
                except Exception as exc:  # report tool failures to the model, not the user
                    out = {"error": str(exc)}
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": _json(out)})
        msgs.append({"role": "user", "content": results})
    yield {"type": "delta", "text": "\n\nI couldn't finish looking that up. Please try a narrower question."}


def _json(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))


def limit_words(text: str, limit: int = MAX_WORDS) -> str:
    """Backstop for the prompt's length rule: cut at the last whole line/sentence within `limit` words."""
    if len(text.split()) <= limit:
        return text
    out, count = [], 0
    for line in text.split("\n"):
        n = len(line.split())
        if count + n <= limit:
            out.append(line)
            count += n
            continue
        if not out or not "".join(out).strip():  # a single huge paragraph: keep whole sentences
            for sent in line.replace(". ", ".\u0000").split("\u0000"):
                k = len(sent.split())
                if count + k > limit:
                    break
                out.append(sent + " ")
                count += k
        break
    return "\n".join(out).strip()


_FOLLOWUP = re.compile(r"\b(it|that|this|those|these|them|more|why|elaborate|explain|continue|again|also|"
                       r"previous|earlier|above)\b|^(and|so|but|what about|how about)\b")


def cache_key(message: str) -> str | None:
    """Normalised question for answer reuse; None for short or follow-up style messages."""
    q = re.sub(r"[^a-z0-9 ]+", " ", message.lower())
    q = re.sub(r"\s+", " ", q).strip()
    if len(q.split()) < 4 or _FOLLOWUP.search(q):
        return None
    return q


def chat_events(profile: dict, message: str):
    """Persist the exchange around events(); reuse a same-day answer, or fall back to direct lookups."""
    pid = profile["id"]
    today = date.today().isoformat()  # transit-dependent answers go stale daily
    key = cache_key(message)
    cached = storage.cache_get(pid, key, today) if key else None
    if cached:
        storage.add_message(pid, "user", message)
        storage.add_message(pid, "assistant", cached)
        storage.log_usage(pid, "cache", message, words=len(cached.split()))
        yield {"type": "delta", "text": cached}
        yield {"type": "done", "mode": "cache"}
        return

    history = storage.get_messages(pid)
    parts: list[str] = []
    mode = "llm"
    use = {"model": None, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "rounds": 0}
    try:
        for ev in events(profile, history, message):
            if ev["type"] == "usage":
                use["model"] = ev["model"]
                use["rounds"] += 1
                for k in ("input", "output", "cache_read", "cache_write"):
                    use[k] += ev[k]
                continue
            if ev["type"] == "delta":
                parts.append(ev["text"])
            yield ev
    except RuntimeError:  # no key / SDK missing: still answer simple data questions
        direct = ask.lookup(profile["chart"], message)
        if direct is None:
            raise
        parts, mode = [direct], "lookup"
        yield {"type": "delta", "text": direct}
    text = "".join(parts).strip()
    trimmed = limit_words(text) if mode == "llm" else text
    if trimmed != text:
        text = trimmed
        yield {"type": "replace", "text": text}
    if not text:  # never store or show a blank answer
        raise RuntimeError("The assistant didn't produce an answer. Please try again.")
    storage.add_message(pid, "user", message)
    storage.add_message(pid, "assistant", text)
    storage.log_usage(pid, mode, message, model=use["model"], input_tokens=use["input"],
                      output_tokens=use["output"], cache_read=use["cache_read"], cache_write=use["cache_write"],
                      tool_rounds=use["rounds"], words=len(text.split()))
    if mode == "llm" and key:
        storage.cache_put(pid, key, today, text)
    yield {"type": "done", "mode": mode}


def chat(profile: dict, message: str) -> dict:
    """Non-streaming convenience wrapper around chat_events()."""
    text, mode = [], "llm"
    for ev in chat_events(profile, message):
        if ev["type"] == "delta":
            text.append(ev["text"])
        elif ev["type"] == "replace":
            text = [ev["text"]]
        elif ev["type"] == "done":
            mode = ev["mode"]
    return {"mode": mode, "reply": "".join(text).strip()}
