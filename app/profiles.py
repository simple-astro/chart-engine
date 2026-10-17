"""Routes for saved birth profiles and chatting about them."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app import access, chat, config, storage
from app.routes import chart as compute_chart
from app.routes import with_extras
from app.schemas import ChartRequest

router = APIRouter(prefix="/profiles", tags=["profiles"])
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
    owner = _owner(request)
    limit, used = _tester_limit(owner), storage.llm_requests_today(owner)
    return {"limited": True, "limit": limit, "used": used, "left": max(0, limit - used)}


def _check_quota(request: Request) -> None:
    """Daily caps on paid chat turns; active only when the tester gate is on."""
    if not access.enabled():
        return
    owner = _owner(request)
    per_tester = _tester_limit(owner)
    total = config.get("daily_limit_total")
    if storage.llm_requests_today(owner) >= per_tester or storage.llm_requests_today() >= total:
        raise HTTPException(status_code=429, detail="You've reached today's question limit for the test version. "
                                                    "Please come back tomorrow.")


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
    return p


def _transit_tz(p: dict, tz: str | None) -> str:
    """The viewer's time zone if given (transits follow where they are now), else the birthplace's."""
    from zoneinfo import ZoneInfo
    name = tz or p["request"].get("tz_name") or "UTC"
    try:
        ZoneInfo(name)
    except Exception as exc:  # unknown or malformed zone name
        raise HTTPException(status_code=422, detail="unknown time zone") from exc
    return name


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


@router.get("/{profile_id}/kp/{topic}")
def kp_prediction(profile_id: int, topic: str, request: Request, months: int = 24) -> dict:
    from core import kp_predict
    if topic not in kp_predict.TOPICS:
        raise HTTPException(status_code=422, detail=f"Unknown topic. Use one of: {', '.join(kp_predict.TOPICS)}")
    p = _require(profile_id, request)
    return kp_predict.predict(p["chart"], topic, months=max(1, min(60, months)))


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


@router.get("/{profile_id}/chat")
def chat_history(profile_id: int, request: Request) -> list[dict]:
    _require(profile_id, request)
    return storage.get_messages(profile_id)


def _with_here(profile: dict, req: ChatRequest) -> dict:
    return {**profile, "viewer": req.here.model_dump()} if req.here else profile


@router.post("/{profile_id}/chat")
def chat_send(profile_id: int, req: ChatRequest, request: Request) -> dict:
    profile = _with_here(_require(profile_id, request), req)
    _check_quota(request)
    try:
        return chat.chat(profile, req.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # upstream API failure
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc


@router.post("/{profile_id}/chat/stream")
def chat_stream(profile_id: int, req: ChatRequest, request: Request) -> StreamingResponse:
    """Newline-delimited JSON events: status / delta / done / error."""
    profile = _with_here(_require(profile_id, request), req)
    _check_quota(request)

    def gen():
        try:
            for ev in chat.chat_events(profile, req.message):
                yield json.dumps(ev) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"

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
    events = [{**e, "label": L.KINDS[e["kind"]][0],
               "check": L.check(chart, e["kind"], date.fromisoformat(e["date"]), e["precision"])}
              for e in storage.event_list(p["id"])]
    return {"kinds": [{"key": k, "label": v[0]} for k, v in L.KINDS.items()], "events": events,
            "summary": L.summary(chart, events, birth, today)}


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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
