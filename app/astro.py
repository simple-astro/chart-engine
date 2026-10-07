"""Additional astrology branches: Lal Kitab, Ashtakoota match-making and daily muhurat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from datetime import date

from pydantic import BaseModel, Field

from app import muhurat, storage
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import lalkitab, matchmaking

router = APIRouter(tags=["astrology"])


class MuhuratRequest(BaseModel):
    start: date
    days: int = Field(default=1, ge=1, le=14)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz_name: str
    birth_nakshatra: int | None = Field(default=None, ge=0, le=26)
    birth_moon_sign: int | None = Field(default=None, ge=0, le=11)


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



@router.post("/muhurat")
def daily_muhurat(req: MuhuratRequest) -> dict:
    try:
        days = muhurat.muhurat_days(req.start, req.days, req.lat, req.lon, req.tz_name,
                                    req.birth_nakshatra, req.birth_moon_sign)
    except Exception as exc:  # bad timezone or polar day without sunrise
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tz_name": req.tz_name, "days": days}
