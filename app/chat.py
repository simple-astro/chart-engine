"""Chat assistant over a saved chart: Claude with tools for live transits, panchang and detail lookups."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone

from app import ask, config, storage
from app.schemas import PanchangRequest, TransitRequest, TransitScanRequest

MAX_TOOL_ROUNDS = 6
HISTORY_LIMIT = 6
# Output budget per model call. Haiku 4.5 runs without thinking, so a few hundred words need ~1500.
# The newer models always think first and thinking counts against max_tokens, so they get more room.
MAX_TOKENS = 1500
MAX_TOKENS_THINKING = 8000

SYSTEM = (
    "You are Sukh, the AI Jyotishi of SimpleJyotish, chatting with the owner of the birth chart below. You were "
    "built on the Nadi method of the founder, Sukhdeep Singh (practising since 2014), so people have a trusted "
    "Jyotishi at any hour, with no appointment and no judgment. You are an AI, not a human — if asked, say so "
    "plainly and never claim to be Sukhdeep.\n"
    "Voice: a caring family Jyotishi — warm, calm and reassuring, in simple English. Use familiar Hindi words "
    "(dasha, upay, shubh, muhurat) with a short meaning the first time. Say 'Namaste' only when opening a new "
    "conversation.\n"
    "People come with a worry or a decision, not to study their chart. Give them clarity and something to do: "
    "lead with the plain answer, then practical guidance — what to do, what to avoid, and one or two simple upay "
    "(remedies) that fit their chart. Give the astrological reason in one short line (e.g. 'because Saturn rules "
    "your career house'); skip degrees, KP sub-lords and technical terms unless they ask for them.\n"
    "Answer ANY question about their kundli: personality, career, marriage, health tendencies, finances, "
    "education, dasha timing, transits, muhurta, divisional charts, Lal Kitab upay, guna milan, or how a concept "
    "works. Ground every answer in the chart data — never state a planetary position you have not been given.\n"
    "The chart data is pre-synthesised. 'planets' carry dignity, nature (benefic/malefic), the houses they own, "
    "conjunctions ('with'), drishti received ('aspected_by') and Neecha Bhanga; 'houses' list the factors raising "
    "(+) and lowering (-) each house with a net verdict; 'dasha' is what runs now and next, and dasha.next_24_months "
    "lists every maha/antar/pratyantar period with its start and end dates — quote dates only from it, and name the "
    "level correctly (a pratyantar is a sub-period inside the antardasha, not a new antardasha); 'transits_now' is today's "
    "sky from the lagna and the Moon (with Sade Sati if active). Houses are whole-sign from the lagna; the 'kp' block "
    "uses Placidus cusps.\n"
    "SYNTHESISE, never read one placement in isolation: for any matter, weigh the + and - of its houses, the dignity "
    "and drishti on their lords and occupants, the yogas involved, and whether the running daśā lords own or occupy "
    "those houses — then explain the balance (e.g. 'Saturn in the 7th delays marriage, but it is exalted and "
    "Jupiter aspects it, so marriage may come late and be very stable'). For questions about now or the coming "
    "months, anchor in the maha/antar daśā and transits_now. Use the dignity, drishti, yogas and Neecha Bhanga "
    "exactly as given; never infer or contradict them. When a KP prediction is supplied (or fetched with "
    "get_kp_prediction), it is the verdict: say whether the matter is promised and which windows are strong or "
    "challenging exactly as computed, explain why through the star lord (what the period gives) and the sub lord "
    "(whether it delivers) in plain words, and never upgrade or downgrade a window. When asked for an exact date or "
    "day, call get_event_days and give only the dates it returns, with their transit reasons. A RISK reading (illness, "
    "accident, dispute, separation, career loss) is a period to take care in, never a certainty: say so gently, "
    "never alarm, and pair it with practical steps and an upay. For upay follow remedy_guide: mantras and daan on the "
    "planet's own day, and gemstones only from suitable_stones. "
    "For questions about the "
    "present or future, call the tools (transits, transit events, panchang, dasha detail, divisional charts, "
    "Lal Kitab kundli) instead of guessing positions. For Lal Kitab questions call get_lal_kitab; for "
    "compatibility or match-making call list_profiles then match_with_profile.\n"
    "Length: HARD LIMIT of {words} words per reply, counting headings and bullets; aim well under it. "
    "Lead with the direct answer, then Do's, Don'ts and an upay; skip exhaustive lists, and offer to go deeper "
    "on one point instead of covering everything.\n"
    "Style: warm and conversational, never stiff; clear short bullets when helpful. Frame outcomes as tendencies, "
    "never certainties; do not give medical, legal or financial advice, and for a high-stakes or sensitive "
    "decision say a review with the founding astrologer is worth it. If the question is unrelated to astrology or "
    "the chart, politely steer back. Today's date is given in the data.\n\nCHART DATA (JSON):\n"
)

# Bump when the chart context or prompt changes meaningfully, so cached answers from the old setup aren't reused.
CONTEXT_VERSION = "nadi-3"

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
    {"name": "get_lal_kitab",
     "description": "The native's Lal Kitab kundli: house placements, pakka ghar/exalted/debilitated/sleeping "
                    "planet status, debts (rin) and traditional remedies per planet. Use for any Lal Kitab question.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_profiles",
     "description": "Saved profiles (id, name, birth date) that can be used as a match-making partner.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "match_with_profile",
     "description": "Ashtakoota (36-point) Guna Milan and Manglik check between the native and another saved profile.",
     "input_schema": {"type": "object", "properties": {
         "partner_id": {"type": "integer", "description": "Profile id from list_profiles"},
         "native_role": {"type": "string", "enum": ["groom", "bride"],
                         "description": "Whether the native is the groom or the bride"}},
         "required": ["partner_id", "native_role"]}},
    {"name": "get_kp_prediction",
     "description": "Computed KP verdicts for a life matter: whether it is promised and which dasha windows "
                    "(maha/antar/pratyantar) are strong, favourable, mixed or challenging, with reasons.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string", "enum": list(__import__("core.kp_predict", fromlist=["TOPICS"]).TOPICS)},
         "months": {"type": "integer", "description": "How far ahead, 1-60. Default 24."}}, "required": ["topic"]}},
    {"name": "get_event_days",
     "description": "Most likely exact days for a life matter in a date range, from the transit rules (a significator "
                    "over a natal significator or a combination cusp within 1°, two significators conjoined, the Moon "
                    "joining three, the Antar lord in a significator's star), inside DBA windows that allow it.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string", "enum": list(__import__("core.kp_predict", fromlist=["TOPICS"]).TOPICS)},
         "start": {"type": "string", "description": "YYYY-MM-DD; default today"},
         "days": {"type": "integer", "description": "How many days to scan, 1-366. Default 90."}}, "required": ["topic"]}},
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
    if name == "get_lal_kitab":
        from app import astro
        return astro.lal_kitab_for(req)
    if name == "list_profiles":
        return {"profiles": [{"id": p["id"], "name": p["name"], "dob": p["request"]["dob"]}
                             for p in storage.list_all(profile.get("owner")) if p["id"] != profile["id"]]}
    if name == "match_with_profile":
        from app import astro
        me, other = profile["id"], int(args["partner_id"])
        groom, bride = (me, other) if args.get("native_role") == "groom" else (other, me)
        return astro.match_for(groom, bride, profile.get("owner"))
    if name == "get_kp_prediction":
        from core import kp_predict
        months = max(1, min(60, int(args.get("months") or 24)))
        return {"brief": kp_predict.brief(kp_predict.predict(chart, str(args.get("topic")), months=months))}
    if name == "get_event_days":
        from datetime import date as _d
        from core import kp_predict
        start = _d.fromisoformat(args["start"]) if args.get("start") else None
        return kp_predict.event_days(chart, str(args.get("topic")), start, int(args.get("days") or 90),
                                     (profile.get("request") or {}).get("tz_name") or "UTC")
    if name == "get_dasha_detail":
        md = next((d for d in chart["dasha"] if d["lord"].lower() == str(args.get("mahadasha", "")).lower()), None)
        if not md:
            return {"error": "No such mahadasha in this chart"}
        from app.synthesis import flat_periods
        return {"maha": md["lord"], "starts": md["start"][:10], "ends": md["end"][:10],
                "periods": flat_periods(md)}
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
    "get_kp_prediction": "Working out the KP timing…",
    "get_event_days": "Finding the likely days…",
    "get_lal_kitab": "Reading your Lal Kitab kundli…",
    "list_profiles": "Checking saved profiles…",
    "match_with_profile": "Matching the two charts…",
}


def _stream(client, model: str, **kw):
    """Haiku 4.5 takes a plain request. The 5.x models always think, so give them room, keep chat at low
    effort, and opt into server-side refusal fallbacks so a declined question is answered by another model."""
    if model == "claude-haiku-4-5":
        return client.messages.stream(model=model, max_tokens=MAX_TOKENS, **kw)
    return client.beta.messages.stream(model=model, max_tokens=MAX_TOKENS_THINKING,
                                       output_config={"effort": "low"},
                                       betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)


def events(profile: dict, history: list[dict], message: str):
    """Run one chat turn, yielding {"type": "status"|"delta", "text": ...} as it progresses."""
    client = _client()
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_LIMIT:]]
    msgs.append({"role": "user", "content": message + kp_context(profile, message)})
    system = _system(profile)
    model = config.model()
    wrote = False
    for _ in range(MAX_TOOL_ROUNDS):
        with _stream(client, model, system=system, tools=TOOLS, messages=msgs) as stream:
            for text in stream.text_stream:
                yield {"type": "delta", "text": text}
                wrote = wrote or bool(text.strip())
            resp = stream.get_final_message()
        u = getattr(resp, "usage", None)
        yield {"type": "usage", "model": getattr(resp, "model", None) or model, "round": 1,
               "input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
               "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
               "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        if resp.stop_reason == "refusal":
            yield {"type": "delta", "text": ("\n\n" if wrote else "") + "I can't help with that question. "
                   "Please ask me something else about your chart."}
            return
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
                yield {"type": "tool_out", "data": out, "name": b.name, "args": b.input or {}}
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": _json(out)})
        msgs.append({"role": "user", "content": results})
    yield {"type": "delta", "text": "\n\nI couldn't finish looking that up. Please try a narrower question."}


def kp_context(profile: dict, message: str) -> str:
    """Computed KP verdicts for the matters the question is about, appended to the user turn (not stored)."""
    from core import kp_predict
    briefs = [kp_predict.brief(kp_predict.predict(profile["chart"], t)) for t in kp_predict.topics_for(message)]
    if not briefs:
        return ""
    return ("\n\n[Computed KP prediction for this question — take every verdict and window date from here and "
            "explain the reasons in plain words]\n" + "\n\n".join(briefs))


def _system(profile: dict) -> list[dict]:
    text = SYSTEM.format(words=config.word_limit()) + ask.llm_context(profile)
    remarks = storage.tester_remarks(profile.get("owner"))
    if remarks:
        text += f"\n\n[CONTEXT NOTE: {remarks}]"
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def revise(profile: dict, history: list[dict], message: str, draft: str, note: str) -> tuple[str, dict]:
    """One correction pass: show the model its draft and the contradictions, get a fixed answer back."""
    client, model = _client(), config.model()
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_LIMIT:]]
    msgs += [{"role": "user", "content": message}, {"role": "assistant", "content": draft},
             {"role": "user", "content": note}]
    with _stream(client, model, system=_system(profile), messages=msgs) as stream:
        resp = stream.get_final_message()
    u = getattr(resp, "usage", None)
    use = {"input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
           "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
           "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip(), use


def guard(profile: dict, history: list[dict], message: str, text: str, tool_outs: list):
    """Check the answer against the chart; revise once, then drop any sentence that is still wrong.
    Yields status events and finally {"type": "checked", "text", "report", "usage"}."""
    from app import factcheck, synthesis
    from core import kp_predict
    topics = set(kp_predict.topics_for(message)) | {str(t["args"].get("topic")) for t in tool_outs
                                                     if t.get("name") == "get_kp_prediction"}
    kp = {t: kp_predict.predict(profile["chart"], t) for t in topics if t in kp_predict.TOPICS}
    facts = factcheck.facts_from(synthesis.build(profile), profile["chart"], [t["data"] for t in tool_outs], kp)
    issues = factcheck.check(text, facts)
    report = {"found": [f"{i['claim']} → {i['truth']}" for i in issues], "revised": False, "removed": []}
    use = None
    if issues:
        yield {"type": "status", "text": "Double-checking against your chart…"}
        try:
            fixed, use = revise(profile, history, message, text, factcheck.correction_note(issues))
        except Exception:  # if the correction call fails, fall back to removing the wrong sentences
            fixed = ""
        if fixed:
            report["revised"] = True
            text, issues = fixed, factcheck.check(fixed, facts)
        if issues:
            report["removed"] = [i["sentence"] for i in issues]
            text = factcheck.strip(text, issues)
    yield {"type": "checked", "text": text, "report": report, "usage": use}


def _json(obj) -> str:
    import json
    return json.dumps(obj, separators=(",", ":"))


def limit_words(text: str, limit: int) -> str:
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
    key = key and f"{CONTEXT_VERSION}:{key}"
    cached = storage.cache_get(pid, key, today) if key else None
    if cached:  # re-verify: a cached answer must still pass the current fact check
        from app import factcheck, synthesis
        if factcheck.check(cached, factcheck.facts_from(synthesis.build(profile), profile["chart"])):
            cached = None
    if cached:
        storage.add_message(pid, "user", message)
        storage.add_message(pid, "assistant", cached)
        storage.log_usage(pid, "cache", message, words=len(cached.split()), owner=profile.get("owner"),
                          answer=cached)
        yield {"type": "delta", "text": cached}
        yield {"type": "done", "mode": "cache"}
        return

    history = storage.get_messages(pid)
    parts: list[str] = []
    tool_outs: list = []
    mode = "llm"
    report = None
    use = {"model": None, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "rounds": 0}
    # Drafts are held back until checked against the chart, so the user only ever sees verified text.
    yield {"type": "status", "text": "Reading your chart…"}
    try:
        for ev in events(profile, history, message):
            if ev["type"] == "usage":
                use["model"] = ev["model"]
                use["rounds"] += 1
                for k in ("input", "output", "cache_read", "cache_write"):
                    use[k] += ev[k]
                continue
            if ev["type"] == "tool_out":
                tool_outs.append(ev)
                continue
            if ev["type"] == "delta":
                if not parts:
                    yield {"type": "status", "text": "Writing your answer…"}
                parts.append(ev["text"])
                continue
            yield ev
    except RuntimeError:  # no key / SDK missing: still answer simple data questions
        direct = ask.lookup(profile["chart"], message)
        if direct is None:
            raise
        parts, mode = [direct], "lookup"
    text = "".join(parts).strip()
    if mode == "llm" and text:
        for ev in guard(profile, history, message, text, tool_outs):
            if ev["type"] != "checked":
                yield ev
                continue
            text, report = ev["text"], ev["report"]
            if ev["usage"]:
                use["rounds"] += 1
                for k in ("input", "output", "cache_read", "cache_write"):
                    use[k] += ev["usage"][k]
        text = limit_words(text, config.word_limit())
    if not text:  # never store or show a blank answer
        raise RuntimeError("The assistant didn't produce an answer. Please try again.")
    yield {"type": "delta", "text": text}
    storage.add_message(pid, "user", message)
    storage.add_message(pid, "assistant", text)
    storage.log_usage(pid, mode, message, model=use["model"], input_tokens=use["input"],
                      output_tokens=use["output"], cache_read=use["cache_read"], cache_write=use["cache_write"],
                      tool_rounds=use["rounds"], words=len(text.split()), owner=profile.get("owner"),
                      answer=text, factcheck=report)
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
