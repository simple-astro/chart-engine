"""Additional astrology branches: Lal Kitab and Ashtakoota match-making."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import storage
from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import lalkitab, matchmaking

router = APIRouter(tags=["astrology"])


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
