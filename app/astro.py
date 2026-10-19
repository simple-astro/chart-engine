"""Additional astrology branches: Lal Kitab, Ashtakoota match-making and daily muhurat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from app import muhurat, storage, today as today_mod
from app.routes import calc_error, chart as compute_chart, require_tz, with_extras
from app.schemas import ChartRequest
from core import horary, jamakkol, lalkitab, matchmaking

router = APIRouter(tags=["astrology"])


class MuhuratRequest(BaseModel):
    start: date
    days: int = Field(default=1, ge=1, le=14)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str
    birth_nakshatra: int | None = Field(default=None, ge=0, le=26)
    birth_moon_sign: int | None = Field(default=None, ge=0, le=11)
    lagna_sign: int | None = Field(default=None, ge=0, le=11)  # personal colours to wear / avoid


class FindRequest(BaseModel):
    activity: str
    start: date
    days: int = Field(default=30, ge=1, le=90)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str
    birth_nakshatra: int | None = Field(default=None, ge=0, le=26)
    birth_moon_sign: int | None = Field(default=None, ge=0, le=11)


GRAHA = r"^(Sun|Moon|Mars|Mercury|Jupiter|Venus|Saturn|Rahu|Ketu)$"


class TodayRequest(BaseModel):
    date: date
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str
    lagna_sign: int = Field(ge=0, le=11)
    birth_nakshatra: int = Field(ge=0, le=26)
    birth_moon_sign: int = Field(ge=0, le=11)
    maha: str | None = Field(default=None, pattern=GRAHA)
    antar: str | None = Field(default=None, pattern=GRAHA)
    antar_sign: int | None = Field(default=None, ge=0, le=11)  # natal sign of the Antardasha lord
    maha_sign: int | None = Field(default=None, ge=0, le=11)   # natal sign of the Mahadasha lord


class HoraryRequest(BaseModel):
    number: int = Field(ge=1, le=249)
    kind: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    asked_at: datetime | None = None  # defaults to now


class JamakkolRequest(BaseModel):
    kind: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(min_length=1, max_length=64)
    asked_at: datetime | None = None  # defaults to now: Jamakkol is cast for the moment of asking


class MatchRequest(BaseModel):
    groom_id: int
    bride_id: int


def lal_kitab_for(request: dict) -> dict:
    """Lal Kitab uses Lahiri positions; recompute the natal chart that way from a stored request."""
    req = ChartRequest(**{**request, "ayanamsha": "lahiri"})
    return lalkitab.compute_lal_kitab(compute_chart(req))


def match_for(groom_id: int, bride_id: int, owner: str | None = None) -> dict:
    groom, bride = storage.get(groom_id, owner), storage.get(bride_id, owner)
    if not groom or not bride:
        raise HTTPException(status_code=404, detail="Profile not found")
    if groom_id == bride_id:
        raise HTTPException(status_code=422, detail="Choose two different profiles")
    return matchmaking.compute_match(groom["chart"], bride["chart"])


@router.post("/lal-kitab")
def lal_kitab(req: ChartRequest) -> dict:
    return lal_kitab_for(req.model_dump(mode="json"))


@router.post("/matchmaking")
def match(req: MatchRequest, request: Request) -> dict:
    return match_for(req.groom_id, req.bride_id, request.state.owner)



# ----- married life (app/marriage.py): ratings, what helps, talk days and patience days -----
class CoupleUpdate(BaseModel):
    married: bool | None = None
    ratings: dict[str, int] | None = None
    trend: str | None = None
    plan: str | None = None      # "start" or "stop" the 43-day plan
    tick: bool | None = None     # mark today's habit done


def _couple_pair(groom_id: int, bride_id: int, owner):
    groom, bride = storage.get(groom_id, owner), storage.get(bride_id, owner)
    if not groom or not bride or groom_id == bride_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    return groom, bride


def _today(tz: str | None, fallback: str) -> tuple[date, str]:
    from zoneinfo import ZoneInfo
    try:
        z = tz or fallback
        return datetime.now(ZoneInfo(z)).date(), z
    except Exception:
        return datetime.now(ZoneInfo(fallback)).date(), fallback


def couple_view(groom: dict, bride: dict, owner, tz: str | None) -> dict:
    from app import marriage
    from app.remedies import library
    c = storage.couple_get(owner, groom["id"], bride["id"]) or {"married": 0, "ratings": {}, "trend": None,
                                                                  "plan_start": None, "ticks": []}
    m = matchmaking.compute_match(groom["chart"], bride["chart"])
    cmp = marriage.compare(m, c["ratings"])
    today, tz = _today(tz, groom["request"].get("tz_name") or "UTC")
    first = lambda p: (p.get("name") or "").split(" ")[0] or "You"
    names = (first(groom), first(bride))
    wed = [e["date"] for pid in (groom["id"], bride["id"]) for e in storage.event_list(pid) if e["kind"] == "married"]
    wedding = date.fromisoformat(min(wed)) if wed else None
    habits = marriage.habits(cmp["rows"], library.served("couple"))
    day = marriage.plan_day(c["plan_start"], today)
    return {"married": bool(c["married"]), "ratings": c["ratings"], "trend": c["trend"], "trends": marriage.TRENDS,
            "areas": [{"key": k, "label": l, "koota": ko} for k, l, ko in marriage.AREAS], "compare": cmp,
            "habits": habits, "names": names, "today": today.isoformat(),
            "days": marriage.days(groom["chart"], bride["chart"], today, 28, tz, names),
            "wedding": wedding.isoformat() if wedding else None,
            "early_years": marriage.early_years([(names[0], with_extras(groom["chart"])),
                                                 (names[1], with_extras(bride["chart"]))], wedding),
            "plan": {"day": day, "of": marriage.PLAN_DAYS, "habit": habits[0] if habits else None,
                     "done_today": today.isoformat() in c["ticks"],
                     "done": len([t for t in c["ticks"] if c["plan_start"] and t >= c["plan_start"]])} if day else None}


@router.get("/couples/{groom_id}/{bride_id}")
def couple_get(groom_id: int, bride_id: int, request: Request, tz: str | None = None) -> dict:
    groom, bride = _couple_pair(groom_id, bride_id, request.state.owner)
    return couple_view(groom, bride, request.state.owner, tz)


@router.put("/couples/{groom_id}/{bride_id}")
def couple_put(groom_id: int, bride_id: int, req: CoupleUpdate, request: Request, tz: str | None = None) -> dict:
    from app import marriage
    owner = request.state.owner
    groom, bride = _couple_pair(groom_id, bride_id, owner)
    keys = {k for k, _, _ in marriage.AREAS}
    fields = {}
    if req.married is not None:
        fields["married"] = int(req.married)
    if req.ratings is not None:
        if set(req.ratings) - keys or any(not 1 <= v <= 5 for v in req.ratings.values()):
            raise HTTPException(status_code=422, detail="Ratings are 1 to 5 for the six areas")
        fields["ratings"] = req.ratings
    if req.trend is not None:
        if req.trend not in marriage.TRENDS:
            raise HTTPException(status_code=422, detail="Unknown trend")
        fields["trend"] = req.trend
    today, _ = _today(tz, groom["request"].get("tz_name") or "UTC")
    if req.plan == "start":
        fields.update(plan_start=today.isoformat(), ticks=[])
    elif req.plan == "stop":
        fields["plan_start"] = None
    if req.tick:
        c = storage.couple_get(owner, groom_id, bride_id) or {"ticks": []}
        fields["ticks"] = sorted(set(c["ticks"]) | {today.isoformat()})
    storage.couple_save(owner, groom_id, bride_id, **fields)
    return couple_view(groom, bride, owner, tz)


@router.get("/profiles/{profile_id}/couple-day")
def couple_day(profile_id: int, request: Request, tz: str | None = None) -> dict:
    """Today's and tomorrow's talk or patience day for each married couple this chart is part of (for Today)."""
    from app import marriage
    owner = request.state.owner
    if not storage.get(profile_id, owner):
        raise HTTPException(status_code=404, detail="Profile not found")
    out = []
    for c in storage.couples_for(owner, profile_id):
        groom, bride = storage.get(c["groom_id"], owner), storage.get(c["bride_id"], owner)
        if not groom or not bride:
            continue
        today, z = _today(tz, groom["request"].get("tz_name") or "UTC")
        first = lambda p: (p.get("name") or "").split(" ")[0] or "You"
        d = marriage.days(groom["chart"], bride["chart"], today, 2, z, (first(groom), first(bride)))
        out.append({"groom_id": c["groom_id"], "bride_id": c["bride_id"], "names": [first(groom), first(bride)],
                    "today": d[0], "tomorrow": d[1]})
    return {"couples": out}


# ----- birth summary, special points and lagna times (app/birth_extras.py) -----
@router.post("/birth-extras")
def birth_extras(req: ChartRequest) -> dict:
    """Avakhada chakra and special points for a birth (saved or not)."""
    from app import birth_extras as B
    r = req.model_dump(mode="json")
    c = compute_chart(req)
    return {"avakhada": B.avakhada(c, r), "special": B.special_points(c, r)}


@router.get("/lagna-times")
def lagna_times(lat: float, lon: float, tz: str, on: date | None = None, ayanamsha: str = "krishnamurti") -> dict:
    """When each sign rises on a local day (for planning a muhurat by lagna)."""
    from zoneinfo import ZoneInfo
    from app import birth_extras as B
    day = on or datetime.now(ZoneInfo(require_tz(tz))).date()
    return {"date": day.isoformat(), "rises": B.lagna_times(day, lat, lon, tz, ayanamsha)}


@router.post("/horary")
def kp_horary(req: HoraryRequest) -> dict:
    when = req.asked_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise HTTPException(status_code=422, detail="asked_at needs a timezone")
    try:
        return horary.judge(req.number, req.kind, when, req.lat, req.lon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/horary/kinds")
def horary_kinds() -> list[dict]:
    return [{"kind": k, "title": v[0], "house": v[1]} for k, v in horary.QUESTIONS.items()]


@router.post("/jamakkol")
def jamakkol_prashna(req: JamakkolRequest) -> dict:
    when = req.asked_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise HTTPException(status_code=422, detail="asked_at needs a timezone")
    require_tz(req.tz_name)
    try:
        return jamakkol.jamakkol(req.kind, when, req.lat, req.lon, req.tz_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/jamakkol/kinds")
def jamakkol_kinds() -> list[dict]:
    return jamakkol.kinds()


@router.post("/muhurat/find")
def find_muhurat(req: FindRequest) -> dict:
    require_tz(req.tz_name)
    if not any(a["key"] == req.activity for a in muhurat.ACTIVITIES):
        raise HTTPException(status_code=422, detail="Pick one of the listed activities.")
    try:
        return muhurat.find_dates(req.activity, req.start, req.days, req.lat, req.lon, req.tz_name,
                                  req.birth_nakshatra, req.birth_moon_sign)
    except Exception as exc:  # polar day without sunrise
        raise calc_error(exc) from exc


@router.post("/today")
def today(req: TodayRequest) -> dict:
    require_tz(req.tz_name)
    try:
        return today_mod.today(req.date, req.lat, req.lon, req.tz_name, req.lagna_sign, req.birth_nakshatra,
                               req.birth_moon_sign, req.maha, req.antar, req.antar_sign, req.maha_sign)
    except Exception as exc:  # polar day without sunrise
        raise calc_error(exc) from exc


@router.post("/muhurat")
def daily_muhurat(req: MuhuratRequest) -> dict:
    require_tz(req.tz_name)
    try:
        days = muhurat.muhurat_days(req.start, req.days, req.lat, req.lon, req.tz_name,
                                    req.birth_nakshatra, req.birth_moon_sign, req.lagna_sign, full=True)
    except Exception as exc:  # polar day without sunrise
        raise calc_error(exc) from exc
    return {"tz_name": req.tz_name, "days": days}
