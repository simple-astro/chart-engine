"""Additional astrology branches: Lal Kitab, Ashtakoota match-making and daily muhurat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app import muhurat, storage, today as today_mod
from app.routes import calc_error, chart as compute_chart, require_tz, with_extras
from app.schemas import ChartRequest
from core import constants as C, horary, jamakkol, lalkitab, matchmaking
from core import panchapakshi as pakshi, sarvatobhadra as sbc, shadbala
from core.ephemeris import julian_day
from core.grahas import compute_grahas
from core.panchang import compute_panchang

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


@router.get("/consult")
def consult_link() -> dict:
    """Where Prashna points people to consult an astrologer (Admin › Settings), or null."""
    from app import config
    return {"telegram": config.get("consult_telegram") or None}


@router.get("/mundane")
def mundane_year(year: int, lat: float, lon: float) -> dict:
    """The Hindu New Year and Mesha Sankranti charts for a year at a place (core/mundane.py)."""
    from core import mundane
    if not 1900 <= year <= 2100 or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(status_code=422, detail="Pick a year between 1900 and 2100 and a valid place.")
    return mundane.year_charts(year, lat, lon)


class RulingRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str = Field(min_length=1, max_length=64)
    at: datetime | None = None  # defaults to now


@router.post("/ruling-planets")
def kp_ruling_planets(req: RulingRequest) -> dict:
    """KP ruling planets for a moment and place (core/ruling.py)."""
    from core import ruling
    require_tz(req.tz_name)
    when = req.at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise HTTPException(status_code=422, detail="The time needs a timezone.")
    return ruling.ruling_planets(when, req.lat, req.lon)


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


class PakshiRequest(BaseModel):
    birth: ChartRequest
    date: date
    days: int = Field(default=1, ge=1, le=7)
    lat: float = Field(ge=-90, le=90)       # where the person is now: the day's sunrise and sunset
    lon: float = Field(ge=-180, le=180)
    tz_name: str


def _natal_lahiri(birth: ChartRequest) -> tuple[dict, datetime]:
    """Sun, Moon and lagna by Lahiri (the reckoning Pancha Pakshi and the Sarvatobhadra use) and the birth moment."""
    when = datetime.combine(birth.dob, birth.tob, tzinfo=ZoneInfo(birth.tz_name))
    g = compute_grahas(julian_day(when), "lahiri", node_type=birth.node_type)
    return g, when


def _iso(x):
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, dict):
        return {k: _iso(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_iso(v) for v in x]
    return x


def pakshi_for(birth: ChartRequest, start: date, days: int, lat: float, lon: float, tz_name: str) -> dict:
    g, _ = _natal_lahiri(birth)
    moon, sun = g["Moon"], g["Sun"]
    paksha = pakshi.paksha_of(sun.longitude, moon.longitude)
    bird = pakshi.birth_bird(moon.nakshatra_index, paksha)
    plans = []
    for i in range(days):
        plan = pakshi.day_plan(start + timedelta(days=i), lat, lon, tz_name, bird)
        plans.append({**plan, "best": pakshi.best_windows(plan)})
    now = datetime.now(timezone.utc)
    cur = None
    for plan in [pakshi.day_plan(start - timedelta(days=1), lat, lon, tz_name, bird)] + plans:
        cur = cur or pakshi.at(plan, now)
    return _iso({"bird": bird, "birth_paksha": paksha, "birth_nakshatra": moon.nakshatra, "tz_name": tz_name,
                 "meaning": pakshi.MEANING, "days": plans,
                 "now": cur and {"activity": cur["yama"]["activity"], "sub": cur["sub"]["activity"],
                                 "sub_bird": cur["sub"]["bird"], "rating": cur["sub"]["rating"],
                                 "until": cur["sub"]["end"], "yama_until": cur["yama"]["end"]}})


@router.post("/panchapakshi")
def panchapakshi(req: PakshiRequest) -> dict:
    require_tz(req.tz_name)
    require_tz(req.birth.tz_name)
    try:
        return pakshi_for(req.birth, req.date, req.days, req.lat, req.lon, req.tz_name)
    except Exception as exc:  # polar day without sunrise
        raise calc_error(exc) from exc


class SbcRequest(BaseModel):
    birth: ChartRequest
    start: date
    days: int = Field(default=14, ge=1, le=31)
    tz_name: str


def sbc_for(birth: ChartRequest, start: date, days: int, tz_name: str) -> dict:
    g, when = _natal_lahiri(birth)
    lagna = compute_chart(ChartRequest(**{**birth.model_dump(), "ayanamsha": "lahiri"}))["lagna"]["sign_index"]
    sunrise = compute_panchang(birth.dob, birth.lat, birth.lon, birth.tz_name).sunrise
    born = when if when >= sunrise else when - timedelta(days=1)  # before sunrise: still the Hindu day before
    weekday = C.WEEKDAY_NAMES[(born.weekday() + 1) % 7]
    pts = sbc.natal_points(g["Moon"].longitude, g["Sun"].longitude, lagna, weekday)
    marks: dict = {}
    for name, rc in pts.items():
        marks.setdefault(rc, []).append(name)
    today_sky = sbc.sky(datetime.combine(start, datetime.min.time().replace(hour=12), tzinfo=ZoneInfo(tz_name)))
    return {"points": {k: list(v) for k, v in pts.items()}, "grid": sbc.grid_view(today_sky, marks),
            "money_days": sbc.money_days(pts, start, days, tz_name)}


@router.post("/sarvatobhadra")
def sarvatobhadra(req: SbcRequest) -> dict:
    require_tz(req.tz_name)
    require_tz(req.birth.tz_name)
    try:
        return sbc_for(req.birth, req.start, req.days, req.tz_name)
    except Exception as exc:
        raise calc_error(exc) from exc


GOODS_KEY = "sbc.goods"


def sbc_goods() -> dict[int, str]:
    try:
        raw = json.loads(storage.get_setting(GOODS_KEY) or "{}")
        return {int(k): str(v) for k, v in raw.items() if 0 <= int(k) < 28}
    except (ValueError, TypeError):
        return {}


@router.get("/sarvatobhadra/market")
def sbc_market(on: date, tz_name: str) -> dict:
    require_tz(tz_name)
    rows = sbc.market(datetime.combine(on, datetime.min.time().replace(hour=12), tzinfo=ZoneInfo(tz_name)),
                      sbc_goods())
    grid = sbc.grid_view(sbc.sky(datetime.combine(on, datetime.min.time().replace(hour=12), tzinfo=ZoneInfo(tz_name))))
    return {"date": on.isoformat(), "rows": rows, "grid": grid, "has_goods": any(r["goods"] for r in rows)}


def _r2(x):
    if isinstance(x, float):
        return round(x, 2)
    if isinstance(x, dict):
        return {k: _r2(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_r2(v) for v in x]
    return x


@router.post("/shadbala")
def shadbala_view(req: ChartRequest) -> dict:
    """Shadbala and Bhava Bala in virupas, for study (core/shadbala.py)."""
    require_tz(req.tz_name)
    try:
        when = datetime.combine(req.dob, req.tob, tzinfo=ZoneInfo(req.tz_name))
        return _r2(shadbala.compute(when, req.lat, req.lon))
    except Exception as exc:
        raise calc_error(exc) from exc
