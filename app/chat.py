"""Chat assistant over a saved chart: Claude with tools for live transits, panchang and detail lookups."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

from app import ask, storage
from app.schemas import PanchangRequest, TransitRequest, TransitScanRequest

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOOL_ROUNDS = 6
HISTORY_LIMIT = 20

SYSTEM = (
    "You are a friendly, knowledgeable Vedic astrology (Jyotish, KP-aware) assistant chatting with the "
    "owner of the birth chart below. Answer ANY question they ask about their chart: personality, "
    "career, marriage, health tendencies, finances, education, dasha timing, transits, divisional "
    "charts, panchang, remedies, or how astrological concepts work. Ground every answer in the chart "
    "data and name the placements, lords, KP significators and dasha periods you rely on. For "
    "questions about the present or future, call the tools (transits, transit events, panchang, "
    "dasha detail, divisional charts) instead of guessing positions.\n"
    "Style: conversational, concise, clear headings or bullets when helpful. Frame outcomes as "
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


def reply(profile: dict, history: list[dict], message: str) -> str:
    """Run one chat turn (tool loop included) and return the assistant's text."""
    client = _client()
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_LIMIT:]]
    msgs.append({"role": "user", "content": message})
    system = [{"type": "text", "text": SYSTEM + ask.llm_context(profile),
               "cache_control": {"type": "ephemeral"}}]
    model = os.environ.get("CHART_LLM_MODEL", DEFAULT_MODEL)
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.messages.create(model=model, max_tokens=1500, system=system, tools=TOOLS, messages=msgs)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                try:
                    out = run_tool(profile, b.name, b.input or {})
                except Exception as exc:  # report tool failures to the model, not the user
                    out = {"error": str(exc)}
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": _json(out)})
        msgs.append({"role": "user", "content": results})
    return "I couldn't finish looking that up. Please try rephrasing or asking something narrower."


def _json(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))


def chat(profile: dict, message: str) -> dict:
    """Persist the user's message, get the reply (LLM, or a direct lookup if no key), persist it."""
    pid = profile["id"]
    history = storage.get_messages(pid)
    try:
        text, mode = reply(profile, history, message), "llm"
    except RuntimeError as exc:  # no key / SDK missing: still answer simple data questions
        direct = ask.lookup(profile["chart"], message)
        if direct is None:
            raise
        text, mode = direct, "lookup"
    storage.add_message(pid, "user", message)
    storage.add_message(pid, "assistant", text)
    return {"mode": mode, "reply": text}
