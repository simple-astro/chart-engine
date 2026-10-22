"""Routes for saved birth profiles and chatting about them."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app import access, chat, config, storage
from app.routes import chart as compute_chart
from app.routes import with_extras
from app.schemas import ChartRequest

router = APIRouter(prefix="/profiles", tags=["profiles"])
log = logging.getLogger(__name__)
CHAT_ERROR = "Astropositivism couldn't answer just now. Please try again in a minute."
usage_router = APIRouter(tags=["usage"])


@usage_router.get("/usage")
def usage(request: Request, recent: int = 20) -> dict:
    """Token usage by request type (llm / cache / lookup) plus the latest requests. Admin only."""
    if not request.state.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return storage.usage_summary(max(1, min(recent, 200)))


class Here(BaseModel):
    """Where the user is now (the app's shared location setting): muhurat times and 'today' follow it."""
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(max_length=64)
    name: str | None = Field(default=None, max_length=80)

    @field_validator("tz_name")
    @classmethod
    def _known_zone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(v)
        except Exception as exc:
            raise ValueError("unknown time zone") from exc
        return v


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    here: Here | None = None
    level: str | None = Field(default=None, pattern=r"^(guide|learn|full)$")  # the reader's level (index.html)


def _owner(request: Request) -> str | None:
    return request.state.owner


def _require(profile_id: int, request: Request) -> dict:
    p = storage.get(profile_id, _owner(request))
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


def _tester_limit(owner: str | None) -> int:
    own = storage.owner_daily_limit(owner)  # set per access code in the admin page; else the default
    return own if own is not None else config.get("daily_limit_per_tester")


@usage_router.get("/quota")
def quota(request: Request) -> dict:
    """How many AI questions this tester has left today, for the Ask Astropositivism header."""
    if not access.enabled() or request.state.admin:
        return {"limited": False}
    from datetime import datetime, time, timedelta, timezone
    owner = _owner(request)
    limit, used = _tester_limit(owner), storage.llm_requests_today(owner)
    shared_out = storage.llm_requests_today() >= config.get("daily_limit_total")  # everyone's cap for the day
    # Counts are per UTC day (storage.llm_requests_today), so they refill at the next UTC midnight.
    resets = datetime.combine(datetime.now(timezone.utc).date() + timedelta(days=1), time(0), tzinfo=timezone.utc)
    return {"limited": True, "limit": limit, "used": used, "left": 0 if shared_out else max(0, limit - used),
            "resets_at": resets.isoformat()}


def _check_quota(request: Request) -> None:
    """Daily caps on paid chat turns; active only when the tester gate is on."""
    if not access.enabled():
        return
    owner = _owner(request)
    per_tester = _tester_limit(owner)
    total = config.get("daily_limit_total")
    mine = storage.llm_requests_today(owner) >= per_tester
    if mine or storage.llm_requests_today() >= total:
        raise HTTPException(status_code=429, detail=(
            (f"You've used today's {per_tester} questions. They refill tomorrow. " if mine else
             "Astropositivism has answered all it can for today in this test version. Questions refill tomorrow. ")
            + "Meanwhile Today, Timing, your charts and remedies are all free to explore."))


@router.post("")
def create_profile(req: ChartRequest, request: Request) -> dict:
    chart = compute_chart(req)  # raises 422 on bad input
    return storage.save(req.name or "Unnamed", req.model_dump(mode="json"), chart, owner=_owner(request))


@router.get("")
def list_profiles(request: Request) -> list[dict]:
    return storage.list_all(_owner(request))


@router.get("/{profile_id}")
def get_profile(profile_id: int, request: Request) -> dict:
    p = _require(profile_id, request)
    with_extras(p["chart"])  # also fills in data for charts saved before it existed
    if "nadi_amsha" not in p["chart"]:
        from core import nadi_amsha
        p["chart"]["nadi_amsha"] = nadi_amsha.analyse(p["chart"], p["request"]["lat"], p["request"]["lon"])
    return p


def _transit_tz(p: dict, tz: str | None) -> str:
    """The viewer's time zone if given (transits follow where they are now), else the birthplace's."""
    from app.routes import require_tz
    return require_tz(tz or p["request"].get("tz_name") or "UTC")


def _transit_day(p: dict, date: str | None, tz: str | None = None):
    from datetime import date as _date, datetime as _dt
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(_transit_tz(p, tz))
    try:
        day = _date.fromisoformat(date) if date else _dt.now(tz).date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc
    if not 1900 <= day.year <= 2100:
        raise HTTPException(status_code=422, detail="date must be between 1900 and 2100")
    return day


@router.get("/{profile_id}/transit")
def transit_overlay(profile_id: int, request: Request, date: str | None = None, tz: str | None = None) -> dict:
    from app import transit_view
    p = _require(profile_id, request)
    return transit_view.overlay(p, _transit_day(p, date, tz), tz_name=_transit_tz(p, tz))


@router.get("/{profile_id}/transit/events")
def transit_events(profile_id: int, request: Request, date: str | None = None, tz: str | None = None) -> dict:
    """Transit significators (planet / star / sub) and the Promise -> Dasha -> Trigger ladder for each life matter."""
    from app import period_view, transit_events as te, transit_view
    p = _require(profile_id, request)
    day = _transit_day(p, date, tz)
    ov = transit_view.overlay(p, day, tz_name=_transit_tz(p, tz))
    return {**te.events(p, day, ov), "periods": period_view.periods(p["chart"], day, ov["dasha"], ov["planets"])}


@router.get("/{profile_id}/paryaya")
def paryaya_rounds(profile_id: int, request: Request) -> dict:
    """Jupiter and Saturn crossing the natal planets and Lagna, from a year ago to three years ahead (core/paryaya.py).
    A hint only: scripts/backtest_paryaya.py found no edge over chance (5/15 book events vs a 29% base rate)."""
    from datetime import date, timedelta
    from core import paryaya
    p = _require(profile_id, request)
    today = chat.local_today(p)
    return {"from": (today - timedelta(days=365)).isoformat(), "to": (today + timedelta(days=3 * 365)).isoformat(),
            "today": today.isoformat(),
            "crossings": paryaya.crossings(p["chart"], today - timedelta(days=365), today + timedelta(days=3 * 365))}


@router.get("/{profile_id}/tajika")
def tajika_year(profile_id: int, request: Request, years: int | None = None) -> dict:
    """Varshaphal (core/tajika.py) for the year that starts ``years`` completed years after birth; by default the
    year running now (the latest Varsha Pravesh before this moment)."""
    from datetime import datetime, timezone
    from core import tajika
    p = _require(profile_id, request)
    if years is None:
        now = datetime.now(timezone.utc)
        years = max(0, tajika.years_for(p["request"], now.date()))
        r = tajika.annual(p["chart"], p["request"], years)
        if datetime.fromisoformat(r["varsha_pravesh"]) > now and years > 0:   # the return is a day or two away
            years -= 1
        elif datetime.fromisoformat(r["next"]) <= now:
            years += 1
        else:
            return {**r, "current": True, "reading": _reading(p, r)}
    try:
        r = tajika.annual(p["chart"], p["request"], years)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Pick a year within 120 years of birth.") from exc
    now = datetime.now(timezone.utc)
    return {**r, "current": datetime.fromisoformat(r["varsha_pravesh"]) <= now < datetime.fromisoformat(r["next"]),
            "reading": _reading(p, r)}


def _reading(p: dict, r: dict) -> dict:
    from app import varshaphal
    return varshaphal.reading(p["chart"], r)


@router.get("/{profile_id}/tajika/polish")
def tajika_polish(profile_id: int, request: Request, years: int) -> dict:
    """The same Varshaphal reading reworded by the AI (app/varshaphal_polish.py), to compare with the rules. For the
    admin while we judge it, or for everyone (Admin › Limits)."""
    from core import tajika
    from app import varshaphal, varshaphal_polish as VP
    mode = config.get("varshaphal_ai")  # Admin › Limits: off, studio or everyone
    if mode == "off" or (mode == "studio" and not request.state.admin):  # "studio": the admin alone, to compare
        raise HTTPException(status_code=403, detail="The AI wording is switched off for now. The rules reading is complete.")
    p = _require(profile_id, request)
    try:
        r = tajika.annual(p["chart"], p["request"], years)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Pick a year within 120 years of birth.") from exc
    reading = varshaphal.reading(p["chart"], r)
    model = config.get("model") if config.provider_of(config.get("model")) == "anthropic" else VP.MODEL
    try:
        out, use = VP.polish(reading, f"{profile_id}|{years}", model)
    except Exception as exc:  # no key, or the AI is unavailable
        raise HTTPException(status_code=503, detail="The AI wording isn't available right now. The rules reading "
                                                    "above is complete.") from exc
    if use:
        storage.log_usage(profile_id, "varshaphal", f"Varshaphal polish, age {years}", model=use["model"],
                          input_tokens=use["input"], output_tokens=use["output"], cache_read=use["cache_read"],
                          cache_write=use["cache_write"], owner=_owner(request))
    return out


@router.get("/{profile_id}/tajika/years")
def tajika_life(profile_id: int, request: Request) -> dict:
    """Life by years (app/varshaphal.py): one line per Varshaphal year from birth to ten years ahead, with the
    person's own events placed in their year and whether that year's chart pointed to them."""
    from app import varshaphal
    p = _require(profile_id, request)
    now = varshaphal.years_now(p["request"], chat.local_today(p))
    rows = varshaphal.life(p["chart"], p["request"], min(110, now + 10), storage.event_list(profile_id))
    return {"now": now, "years": rows}


@router.get("/{profile_id}/kp/{topic}")
def kp_prediction(profile_id: int, topic: str, request: Request, months: int = 24) -> dict:
    from core import kp_predict
    if topic not in kp_predict.TOPICS:
        raise HTTPException(status_code=422, detail=f"Unknown topic. Use one of: {', '.join(kp_predict.TOPICS)}")
    p = _require(profile_id, request)
    return kp_predict.predict(p["chart"], topic, months=max(1, min(60, months)))


@router.get("/{profile_id}/graph/life")
def life_graph(profile_id: int, request: Request, topic: str = "career", ahead: int = 24, back: int = 0) -> dict:
    """The Life graph: for one life matter, the promise of the chart, each Dasha period's strength, the Jupiter and
    Saturn transit month by month, the best windows, and (looking back) the person's own events of that kind, so
    they can see whether their past fell in the lit windows. Same engine as Coming up and the KP timing."""
    from datetime import timedelta
    from core import kp_predict as K
    from app import life_events as L
    if topic not in K.TOPICS:
        raise HTTPException(status_code=422, detail="Choose a life matter from the list.")
    p = _require(profile_id, request)
    chart, today = p["chart"], chat.local_today(p)
    ahead, back = max(6, min(60, ahead)), max(0, min(120, back))
    start = today - timedelta(days=round(back * 30.44))
    r = K.predict(chart, topic, start, back + ahead)
    _, _, good, bad, _, _, kind = K.TOPICS[topic]  # kind "risk": a strong period means more risk (colours flip)
    ayan = chart["meta"].get("ayanamsha", "krishnamurti")
    transit = []
    for i in range(back + ahead):
        mid = start + timedelta(days=round(i * 30.44) + 15)
        w = next((w for w in r["windows"] if w["starts"] <= mid.isoformat() < w["ends"]), None)
        sup = {w[lvl] for lvl in ("maha", "antar", "praty") if w and r["lords"][w[lvl]]["verdict"] in ("supports", "leans good")}
        score, notes = K.transit_trigger(chart, mid, sup, good, bad, ayan)
        transit.append({"date": mid.isoformat(), "score": round(score, 2), "notes": notes})
    events = []
    for e in storage.event_list(profile_id):
        if L.KINDS[e["kind"]][1] != topic:
            continue
        from datetime import date as _d
        d = _d.fromisoformat(e["date"])
        if d < start:
            continue
        events.append({"date": e["date"], "precision": e["precision"], "label": L.KINDS[e["kind"]][0],
                       "fit": L.check(chart, e["kind"], d, e["precision"])["fit"]})
    return {"topic": topic, "kind": kind, "title": r["title"], "houses_for": r["houses_for"], "houses_against": r["houses_against"],
            "significators": r["significators"], "promise": {k: r["promise"][k] for k in ("cusp", "cusp_sub_lord", "signifies", "verdict")},
            "from": r["from"], "to": r["to"], "today": today.isoformat(), "windows": r["windows"], "best": r["best"],
            "best_ahead": [(w["starts"], w["ends"]) for w in sorted(
                (w for w in r["windows"] if w["ends"] > today.isoformat() and w["verdict"] in ("strong", "favourable")),
                key=lambda w: -w["score"])[:3]] if kind == "event" else [],
            "transit": transit, "events": events,
            "topics": [{"key": k, "label": v[0], "kind": v[6]} for k, v in K.TOPICS.items()]}


@router.get("/{profile_id}/kp/{topic}/days")
def kp_event_days(profile_id: int, topic: str, request: Request, start: str | None = None, days: int = 90) -> dict:
    from datetime import date
    from core import kp_predict
    if topic not in kp_predict.TOPICS:
        raise HTTPException(status_code=422, detail=f"Unknown topic. Use one of: {', '.join(kp_predict.TOPICS)}")
    p = _require(profile_id, request)
    try:
        s = date.fromisoformat(start) if start else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="start must be YYYY-MM-DD") from exc
    return kp_predict.event_days(p["chart"], topic, s, max(1, min(366, days)), p["request"].get("tz_name") or "UTC")


@router.put("/{profile_id}")
def update_profile(profile_id: int, req: ChartRequest, request: Request) -> dict:
    _require(profile_id, request)
    chart = compute_chart(req)
    return storage.update(profile_id, req.name or "Unnamed", req.model_dump(mode="json"), chart, _owner(request))


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, request: Request) -> dict:
    if not storage.delete(profile_id, _owner(request)):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": profile_id}


class CheckinAnswer(BaseModel):
    answer: str = Field(pattern="^(well|mixed|poor|notyet)$")


@router.get("/{profile_id}/checkin")
def checkin_due(profile_id: int, request: Request) -> dict:
    """The one "How did it go?" waiting today, if any (app/checkins.py)."""
    from app import checkins
    p = _require(profile_id, request)
    return {"checkin": checkins.due(profile_id, chat.local_today(p))}


@router.post("/{profile_id}/checkin/{checkin_id}")
def checkin_answer(profile_id: int, checkin_id: int, req: CheckinAnswer, request: Request) -> dict:
    from app import checkins
    p = _require(profile_id, request)
    if not checkins.answer(profile_id, checkin_id, req.answer, chat.local_today(p)):
        raise HTTPException(status_code=404, detail="Check-in not found")
    return {"ok": True}


class RatingRequest(BaseModel):
    rating: int = Field(ge=-1, le=1)
    reason: str | None = Field(default=None, max_length=60)


@router.post("/{profile_id}/answers/{usage_id}/rating")
def rate_answer(profile_id: int, usage_id: int, req: RatingRequest, request: Request) -> dict:
    """👍 / 👎 on an answer to this chart (0 clears it). A 👎 puts the answer in the Studio review queue."""
    _require(profile_id, request)
    if not storage.rate_answer(profile_id, usage_id, req.rating or None, req.reason if req.rating == -1 else None):
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"ok": True}


@router.get("/{profile_id}/chat")
def chat_history(profile_id: int, request: Request) -> list[dict]:
    _require(profile_id, request)
    return storage.get_messages(profile_id)


def _with_here(profile: dict, req: ChatRequest) -> dict:
    out = {**profile, "viewer": req.here.model_dump()} if req.here else profile
    return {**out, "level": req.level} if req.level else out


@router.post("/{profile_id}/chat")
def chat_send(profile_id: int, req: ChatRequest, request: Request) -> dict:
    profile = _with_here(_require(profile_id, request), req)
    _check_quota(request)
    try:
        return chat.chat(profile, req.message)
    except RuntimeError as exc:  # server set-up (no API key, missing package)
        log.warning("chat unavailable: %r", exc)
        raise HTTPException(status_code=503, detail=CHAT_ERROR) from exc
    except Exception as exc:  # upstream API failure
        log.warning("chat failed: %r", exc)
        raise HTTPException(status_code=502, detail=CHAT_ERROR) from exc


@router.post("/{profile_id}/chat/stream")
def chat_stream(profile_id: int, req: ChatRequest, request: Request) -> StreamingResponse:
    """Newline-delimited JSON events: status / delta / done / error."""
    profile = _with_here(_require(profile_id, request), req)
    _check_quota(request)

    def gen():
        try:
            for ev in chat.chat_events(profile, req.message):
                yield json.dumps(ev) + "\n"
        except Exception as exc:  # the reason goes to the log; the user gets a plain message
            log.warning("chat stream failed: %r", exc)
            yield json.dumps({"type": "error", "detail": CHAT_ERROR}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.delete("/{profile_id}/chat")
def chat_clear(profile_id: int, request: Request) -> dict:
    _require(profile_id, request)
    storage.clear_messages(profile_id)
    return {"cleared": profile_id}


# ----- state of mind: private mood logs linked to the day's astrology (app/mood.py) -----
class MoodRequest(BaseModel):
    valence: int = Field(ge=-3, le=3)
    feelings: list[str] = Field(default_factory=list, max_length=5)
    causes: list[str] = Field(default_factory=list, max_length=5)
    note: str | None = Field(default=None, max_length=500)
    scope: str = Field(default="now", pattern="^(now|day)$")
    here: Here | None = None

    @field_validator("feelings")
    @classmethod
    def _known_feelings(cls, v: list[str]) -> list[str]:
        from app import mood
        bad = [x for x in v if x not in mood.ALL_FEELINGS]
        if bad:
            raise ValueError(f"unknown feeling: {', '.join(bad)}")
        return list(dict.fromkeys(v))

    @field_validator("causes")
    @classmethod
    def _known_causes(cls, v: list[str]) -> list[str]:
        from app import mood
        bad = [x for x in v if x not in mood.CAUSES]
        if bad:
            raise ValueError(f"unknown cause: {', '.join(bad)}")
        return list(dict.fromkeys(v))


class MoodShare(BaseModel):
    share: bool


MOOD_PER_DAY = 30


@router.get("/{profile_id}/mood")
def mood_log(profile_id: int, request: Request, limit: int = 60) -> dict:
    from app import mood
    _require(profile_id, request)
    return {"logs": [mood.public(x) for x in storage.mood_list(profile_id, max(1, min(limit, 500)))],
            "share": storage.mood_shared(profile_id),
            "options": {"feelings": mood.FEELINGS, "causes": mood.CAUSES, "valence": mood.VALENCE}}


@router.post("/{profile_id}/mood")
def mood_add(profile_id: int, req: MoodRequest, request: Request) -> dict:
    """Save how the person feels with this moment's astrology, and reply with something useful for that mood."""
    from datetime import datetime, timezone
    from app import mood
    profile = _require(profile_id, request)
    w = chat.where({**profile, "viewer": req.here.model_dump()} if req.here else profile)
    now = datetime.now(timezone.utc)
    snap = mood.snapshot(profile, w, now)
    if storage.mood_count_on(profile_id, snap["date"]) >= MOOD_PER_DAY:
        raise HTTPException(status_code=429, detail="That's a lot of logs for one day — try again tomorrow.")
    note = (req.note or "").strip() or None
    care = mood.care_needed(req.valence, note, [{"local_date": snap["date"], "valence": req.valence}]
                            + storage.mood_list(profile_id, 30))
    log = storage.mood_add(profile_id, snap["date"], req.valence, req.feelings, req.causes, note, req.scope, snap)
    return {"log": mood.public(log), "reply": mood.reply(profile, w, log, care)}


@router.get("/{profile_id}/mood/patterns")
def mood_patterns(profile_id: int, request: Request) -> dict:
    from app import mood
    _require(profile_id, request)
    return mood.patterns(storage.mood_list(profile_id))


@router.put("/{profile_id}/mood/share")
def mood_share(profile_id: int, req: MoodShare, request: Request) -> dict:
    """Whether Astropositivism may use the mood log in chat."""
    _require(profile_id, request)
    storage.set_mood_shared(profile_id, req.share)
    return {"share": req.share}


@router.delete("/{profile_id}/mood/{log_id}")
def mood_delete_one(profile_id: int, log_id: int, request: Request) -> dict:
    _require(profile_id, request)
    if not storage.mood_delete(profile_id, log_id):
        raise HTTPException(status_code=404, detail="Log not found")
    return {"deleted": log_id}


@router.delete("/{profile_id}/mood")
def mood_delete_all(profile_id: int, request: Request) -> dict:
    _require(profile_id, request)
    return {"deleted": storage.mood_delete(profile_id)}


# ----- life events: what really happened, checked against the chart (app/life_events.py) -----
class EventRequest(BaseModel):
    kind: str
    year: int = Field(ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, v: str) -> str:
        from app import life_events
        if v not in life_events.KINDS:
            raise ValueError("unknown kind of event")
        return v


def _events_view(p: dict) -> dict:
    from datetime import date
    from app import life_events as L
    chart = with_extras(p["chart"])
    birth, today = date.fromisoformat(p["request"]["dob"]), chat.local_today(p)
    from app import karaka_check as KC
    events = [{**e, "label": L.KINDS[e["kind"]][0],
               "check": L.check(chart, e["kind"], date.fromisoformat(e["date"]), e["precision"]),
               "karaka": KC.check(chart, L.KINDS[e["kind"]][1], *L.span(date.fromisoformat(e["date"]), e["precision"]))}
              for e in storage.event_list(p["id"])]
    summ = L.summary(chart, events, birth, today)
    read = [e for e in L.checked(events)]
    kar = {"fits": sum(e["karaka"]["fit"] == "fits" for e in read), "events": len(read), "note": KC.DRAFT_NOTE,
           "expected": round(sum(KC.base_rate(chart, L.KINDS[e["kind"]][1], birth, today) for e in read), 1),
           "agree": sum(e["check"]["fit"] == "fits" and e["karaka"]["fit"] == "fits" for e in read)} if read else None
    rectified = bool(storage.get_setting(f"rectified_{p['id']}_{p['request'].get('tob', '')[:5]}"))
    group = {k: g for g, ks in L.GROUPS for k in ks}
    return {"kinds": [{"key": k, "label": v[0], "group": group.get(k, "Other")} for k, v in L.KINDS.items()],
            "groups": [g for g, _ in L.GROUPS], "events": events, "summary": summ, "karaka": kar,
            "tob_unknown": bool(p["request"].get("tob_unknown")), "saved_tob": p["request"]["tob"][:5],
            "accuracy": L.accuracy(chart, events, summ, bool(p["request"].get("tob_unknown")), rectified)}


@router.get("/{profile_id}/accuracy")
def chart_accuracy(profile_id: int, request: Request) -> dict:
    """Chart accuracy level and next step (the badge in Studies and the nudge on Today)."""
    return _events_view(_require(profile_id, request))["accuracy"]


@router.get("/{profile_id}/events")
def events_list(profile_id: int, request: Request) -> dict:
    return _events_view(_require(profile_id, request))


@router.post("/{profile_id}/events")
def events_add(profile_id: int, req: EventRequest, request: Request) -> dict:
    from datetime import date
    p = _require(profile_id, request)
    if req.day is not None and req.month is None:
        raise HTTPException(status_code=422, detail="Add the month too, or leave the day out.")
    try:
        d = date(req.year, req.month or 1, req.day or 1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="That date doesn't exist.") from exc
    birth = date.fromisoformat(p["request"]["dob"])
    if d < date(birth.year, birth.month if req.month else 1, 1) or d > chat.local_today(p):
        raise HTTPException(status_code=422, detail="The date must be between your birth and today.")
    if len(storage.event_list(profile_id)) >= 50:
        raise HTTPException(status_code=422, detail="You can keep up to 50 events.")
    storage.event_add(profile_id, req.kind, d.isoformat(), "day" if req.day else "month" if req.month else "year")
    return _events_view(p)


PARTS_OF_DAY = {"night": (0, 359), "morning": (360, 719), "afternoon": (720, 1079), "evening": (1080, 1439)}


class SuggestRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/{profile_id}/events/suggest")
def events_suggest(profile_id: int, req: SuggestRequest, request: Request) -> dict:
    """Life events the person just mentioned in chat, offered for them to confirm. Nothing is saved here."""
    from app import memory
    p = _require(profile_id, request)
    return {"suggestions": memory.suggest(p, req.message, chat.local_today(p))}


@router.get("/{profile_id}/events/birth-time")
def events_birth_time(profile_id: int, request: Request, scope: str = "hour", part: str = "any") -> dict:
    """Which birth times best explain the person's events: an hour either side of the saved time (scope=hour), or
    the whole day, or one part of it, when the time is unknown or doubtful (scope=day, part=night|morning|...)."""
    from app import life_events as L
    p = _require(profile_id, request)
    from app.life_events import checked
    req, events = p["request"], checked(storage.event_list(profile_id))
    unknown = bool(req.get("tob_unknown"))
    if scope not in ("hour", "day") or (part != "any" and part not in PARTS_OF_DAY):
        raise HTTPException(status_code=422, detail="Unknown scope or part of the day.")
    wide = unknown or scope == "day"
    need = 4 if wide else 3
    if len(events) < need:
        raise HTTPException(status_code=422, detail=f"Add at least {need} events to {'find' if unknown else 'rectify'} "
                                                    "your birth time" + (" (with the month if you know it)." if wide else "."))
    at = lambda tob: with_extras(compute_chart(ChartRequest(**{**req, "tob": tob, "tob_unknown": False})))
    out = L.birth_time_check(req, events, at, chat.local_today(p), unknown=unknown,
                             between=PARTS_OF_DAY.get(part) if wide and part != "any" else None)
    out["part"] = part if wide else "any"
    if not wide and out["suggest"] is None:  # the saved time is among the best fits: count it as rectified (for this time only)
        storage.set_setting(f"rectified_{profile_id}_{req['tob'][:5]}", chat.local_today(p).isoformat())
    return out


@router.delete("/{profile_id}/events/{event_id}")
def events_delete(profile_id: int, event_id: int, request: Request) -> dict:
    p = _require(profile_id, request)
    if not storage.event_delete(profile_id, event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return _events_view(p)


# ----- Jamakkol from a chart: ask each question once (81 days), then "did it happen?" -----
JK_VALID_DAYS = 81


class JamakkolAsk(BaseModel):
    kind: str
    question: str | None = Field(default=None, max_length=160)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(min_length=1, max_length=64)
    place: str | None = Field(default=None, max_length=120)  # the place name the asker picked, shown with the answer
    again: bool = False  # "it's a different question": cast even though this kind was asked lately


def _jk_view(a: dict) -> dict:
    from datetime import datetime, timedelta, timezone
    asked = datetime.fromisoformat(a["asked_at"])
    until = asked + timedelta(days=JK_VALID_DAYS)
    return {**a, "valid_until": until.date().isoformat(), "due": datetime.now(timezone.utc) >= until}


@router.get("/{profile_id}/jamakkol")
def jamakkol_asks(profile_id: int, request: Request) -> list[dict]:
    _require(profile_id, request)
    return [_jk_view(a) for a in storage.jk_list(profile_id)]


@router.post("/{profile_id}/jamakkol")
def jamakkol_ask(profile_id: int, req: JamakkolAsk, request: Request) -> dict:
    """Cast now and keep the question; the same kind asked within 81 days answers 409 with the earlier one."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from core import jamakkol
    _require(profile_id, request)
    try:
        ZoneInfo(req.tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Unknown time zone") from exc
    if req.kind not in jamakkol.QUESTIONS:
        raise HTTPException(status_code=422, detail="Unknown question kind")
    if not req.again:
        recent = next((a for a in map(_jk_view, storage.jk_list(profile_id))
                       if a["kind"] == req.kind and not a["due"]), None)
        if recent:
            raise HTTPException(status_code=409, detail={"code": "asked", "ask": recent})
    when = datetime.now(timezone.utc)
    r = jamakkol.jamakkol(req.kind, when, req.lat, req.lon, req.tz_name)
    q = (req.question or "").strip() or None
    a = storage.jk_add(profile_id, req.kind, q, when.isoformat(), req.lat, req.lon, req.tz_name,
                       r["reading"]["verdict"], r["reading"]["label"], (req.place or "").strip() or None)
    return {**r, "ask": _jk_view(a)}


@router.get("/{profile_id}/jamakkol/{ask_id}")
def jamakkol_again(profile_id: int, ask_id: int, request: Request) -> dict:
    """The earlier chart, cast again for the moment and place it was asked (the same answer)."""
    from datetime import datetime
    from core import jamakkol
    _require(profile_id, request)
    a = storage.jk_get(profile_id, ask_id)
    if not a:
        raise HTTPException(status_code=404, detail="Question not found")
    r = jamakkol.jamakkol(a["kind"], datetime.fromisoformat(a["asked_at"]), a["lat"], a["lon"], a["tz_name"])
    return {**r, "ask": _jk_view(a)}


class JamakkolOutcome(BaseModel):
    outcome: str | None = Field(default=None, pattern="^(happened|partly|not)$")


@router.put("/{profile_id}/jamakkol/{ask_id}/outcome")
def jamakkol_outcome(profile_id: int, ask_id: int, req: JamakkolOutcome, request: Request) -> dict:
    _require(profile_id, request)
    if not storage.jk_outcome(profile_id, ask_id, req.outcome):
        raise HTTPException(status_code=404, detail="Question not found")
    return _jk_view(storage.jk_get(profile_id, ask_id))


@router.get("/{profile_id}/upcoming")
def upcoming_changes(profile_id: int, request: Request, tz: str | None = None) -> dict:
    """Coming up for you: the next Dasha period changes and the sky changes that matter to this chart."""
    from app import upcoming
    p = _require(profile_id, request)
    tz_name = _transit_tz(p, tz)
    out = upcoming.upcoming({**p, "chart": with_extras(p["chart"])}, _transit_day(p, None, tz_name), tz_name)
    upcoming.attach_checklists(out["items"], storage.prep_done(profile_id))
    tg = storage.tg_for_profile(profile_id)
    out["telegram"] = {"linked": bool(tg), "reminders": tg["reminders"] if tg else None}
    return out


class PrepTick(BaseModel):
    step: str = Field(min_length=3, max_length=120, pattern=r"^\d{4}-\d{2}-\d{2}\|[a-z_]+\|[bd]\d{1,2}$")
    done: bool


@router.put("/{profile_id}/prep")
def prep_tick(profile_id: int, req: PrepTick, request: Request) -> dict:
    """Tick or untick one "get ready" step."""
    _require(profile_id, request)
    storage.prep_tick(profile_id, req.step, req.done)
    return {"step": req.step, "done": req.done}


# ----- "Just guide me" level (app/goals.py): the year ahead in words, and goal plans -----
@router.get("/{profile_id}/year")
def year_ahead(profile_id: int, request: Request) -> dict:
    from app import goals
    return goals.year_ahead(_require(profile_id, request)["chart"])


@router.get("/{profile_id}/plans")
def plans(profile_id: int, request: Request) -> dict:
    from app import goals
    p = _require(profile_id, request)
    done = storage.goal_steps_done(profile_id)
    mine = [g for g in storage.goals_of(profile_id) if g in goals.GOALS]
    return {"plans": [goals.plan(p["chart"], g, {s for gg, s in done if gg == g}) for g in mine],
            "choices": [{"goal": k, "title": v["title"]} for k, v in goals.GOALS.items() if k not in mine]}


class GoalPick(BaseModel):
    goal: str = Field(min_length=2, max_length=20, pattern=r"^[a-z_]+$")


class GoalTick(BaseModel):
    step: str = Field(min_length=2, max_length=20, pattern=r"^[a-z_]+$")
    done: bool


def _goal(goal: str) -> dict:
    from app import goals
    if goal not in goals.GOALS:
        raise HTTPException(status_code=422, detail="Unknown goal")
    return goals.GOALS[goal]


@router.post("/{profile_id}/plans")
def plan_add(profile_id: int, req: GoalPick, request: Request) -> dict:
    _require(profile_id, request)
    _goal(req.goal)
    storage.goal_add(profile_id, req.goal)
    return {"added": req.goal}


@router.delete("/{profile_id}/plans/{goal}")
def plan_remove(profile_id: int, goal: str, request: Request) -> dict:
    _require(profile_id, request)
    _goal(goal)
    storage.goal_remove(profile_id, goal)
    return {"removed": goal}


@router.put("/{profile_id}/plans/{goal}")
def plan_tick(profile_id: int, goal: str, req: GoalTick, request: Request) -> dict:
    _require(profile_id, request)
    if req.step not in {sid for sid, _ in _goal(goal)["steps"]}:
        raise HTTPException(status_code=422, detail="Unknown step")
    if goal not in storage.goals_of(profile_id):
        raise HTTPException(status_code=404, detail="Add this goal first")
    storage.goal_tick(profile_id, goal, req.step, req.done)
    return {"goal": goal, "step": req.step, "done": req.done}


@router.get("/{profile_id}/upcoming/days")
def upcoming_good_days(profile_id: int, request: Request, activity: str, start: str, days: int = 21,
                       tz: str | None = None, lat: float | None = None, lon: float | None = None) -> dict:
    """The best days to act inside an upcoming window (the muhurat finder for that activity), for where the
    person is (lat/lon/tz from the app's location setting), else the birthplace."""
    from datetime import date
    from app import muhurat
    p = _require(profile_id, request)
    here = lat is not None and lon is not None and tz and -90 <= lat <= 90 and -180 <= lon <= 180
    w = {"lat": lat, "lon": lon} if here else chat.where(p)
    tz_name = _transit_tz(p, tz if here or tz else None)
    try:
        s = date.fromisoformat(start)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="start must be YYYY-MM-DD") from exc
    moon = p["chart"]["grahas"]["Moon"]
    try:
        return muhurat.find_dates(activity, max(s, chat.local_today(p)), max(1, min(days, 45)), w["lat"], w["lon"],
                                  tz_name, moon["nakshatra_index"], moon["sign_index"], limit=3)
    except Exception as exc:  # unknown activity or polar day
        from app.routes import calc_error
        raise calc_error(exc) from exc
