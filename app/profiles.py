"""Routes for saved birth profiles and chatting about them."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _owner(request: Request) -> str | None:
    return request.state.owner


def _require(profile_id: int, request: Request) -> dict:
    p = storage.get(profile_id, _owner(request))
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


def _check_quota(request: Request) -> None:
    """Daily caps on paid chat turns; active only when the tester gate is on."""
    if not access.enabled():
        return
    per_tester, total = config.get("daily_limit_per_tester"), config.get("daily_limit_total")
    if storage.llm_requests_today(_owner(request)) >= per_tester or storage.llm_requests_today() >= total:
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


@router.post("/{profile_id}/chat")
def chat_send(profile_id: int, req: ChatRequest, request: Request) -> dict:
    profile = _require(profile_id, request)
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
    profile = _require(profile_id, request)
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
