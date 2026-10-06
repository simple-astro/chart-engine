"""Additional astrology branches: Lal Kitab and Ashtakoota match-making.

Stateless, like the rest of the engine: every request carries its own birth data.
Nothing is persisted here — the calling platform owns user data.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.routes import chart as compute_chart
from app.schemas import ChartRequest
from core import lalkitab, matchmaking

router = APIRouter(tags=["astrology"])


class MatchRequest(BaseModel):
    groom: ChartRequest
    bride: ChartRequest


@router.post("/lal-kitab")
def lal_kitab(req: ChartRequest) -> dict:
    """Lal Kitab is judged on Lahiri positions regardless of the caller's ayanamsha."""
    return lalkitab.compute_lal_kitab(compute_chart(req.model_copy(update={"ayanamsha": "lahiri"})))


@router.post("/matchmaking")
def match(req: MatchRequest) -> dict:
    return matchmaking.compute_match(compute_chart(req.groom), compute_chart(req.bride))
