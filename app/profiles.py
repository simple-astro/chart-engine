"""Routes for saved birth profiles and asking questions about them."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import ask, storage
from app.routes import chart as compute_chart
from app.schemas import ChartRequest

router = APIRouter(prefix="/profiles", tags=["profiles"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list, max_length=20)


@router.post("")
def create_profile(req: ChartRequest) -> dict:
    chart = compute_chart(req)  # raises 422 on bad input
    return storage.save(req.name or "Unnamed", req.model_dump(mode="json"), chart)


@router.get("")
def list_profiles() -> list[dict]:
    return storage.list_all()


@router.get("/{profile_id}")
def get_profile(profile_id: int) -> dict:
    p = storage.get(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


@router.delete("/{profile_id}")
def delete_profile(profile_id: int) -> dict:
    if not storage.delete(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": profile_id}


@router.post("/{profile_id}/ask")
def ask_profile(profile_id: int, req: AskRequest) -> dict:
    p = storage.get(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    direct = ask.lookup(p["chart"], req.question)
    if direct is not None:
        return {"mode": "lookup", "answer": direct}
    try:
        return {"mode": "llm", "answer": ask.ask_llm(p, req.question, req.history)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # upstream API failure
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc
