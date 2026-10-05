"""Routes for saved birth profiles and chatting about them."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import chat, storage
from app.routes import chart as compute_chart
from app.schemas import ChartRequest

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _require(profile_id: int) -> dict:
    p = storage.get(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


@router.post("")
def create_profile(req: ChartRequest) -> dict:
    chart = compute_chart(req)  # raises 422 on bad input
    return storage.save(req.name or "Unnamed", req.model_dump(mode="json"), chart)


@router.get("")
def list_profiles() -> list[dict]:
    return storage.list_all()


@router.get("/{profile_id}")
def get_profile(profile_id: int) -> dict:
    return _require(profile_id)


@router.delete("/{profile_id}")
def delete_profile(profile_id: int) -> dict:
    if not storage.delete(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": profile_id}


@router.get("/{profile_id}/chat")
def chat_history(profile_id: int) -> list[dict]:
    _require(profile_id)
    return storage.get_messages(profile_id)


@router.post("/{profile_id}/chat")
def chat_send(profile_id: int, req: ChatRequest) -> dict:
    profile = _require(profile_id)
    try:
        return chat.chat(profile, req.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # upstream API failure
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc


@router.delete("/{profile_id}/chat")
def chat_clear(profile_id: int) -> dict:
    _require(profile_id)
    storage.clear_messages(profile_id)
    return {"cleared": profile_id}
