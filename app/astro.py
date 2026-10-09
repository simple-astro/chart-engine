"""Additional astrology branches: Lal Kitab, Ashtakoota match-making and daily muhurat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from app import muhurat, storage, today as today_mod
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import horary, lalkitab, matchmaking

router = APIRouter(tags=["astrology"])


class MuhuratRequest(BaseModel):
    start: date
    days: int = Field(default=1, ge=1, le=14)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str
    birth_nakshatra: int | None = Field(default=None, ge=0, le=26)
    birth_moon_sign: int | None = Field(default=None, ge=0, le=11)


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


class HoraryRequest(BaseModel):
    number: int = Field(ge=1, le=249)
    kind: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    asked_at: datetime | None = None  # defaults to now


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


@router.post("/muhurat/find")
def find_muhurat(req: FindRequest) -> dict:
    try:
        return muhurat.find_dates(req.activity, req.start, req.days, req.lat, req.lon, req.tz_name,
                                  req.birth_nakshatra, req.birth_moon_sign)
    except Exception as exc:  # unknown activity, bad timezone, polar day
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/today")
def today(req: TodayRequest) -> dict:
    try:
        return today_mod.today(req.date, req.lat, req.lon, req.tz_name, req.lagna_sign, req.birth_nakshatra,
                               req.birth_moon_sign, req.maha, req.antar)
    except Exception as exc:  # bad timezone or polar day without sunrise
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/muhurat")
def daily_muhurat(req: MuhuratRequest) -> dict:
    try:
        days = muhurat.muhurat_days(req.start, req.days, req.lat, req.lon, req.tz_name,
                                    req.birth_nakshatra, req.birth_moon_sign)
    except Exception as exc:  # bad timezone or polar day without sunrise
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tz_name": req.tz_name, "days": days}
