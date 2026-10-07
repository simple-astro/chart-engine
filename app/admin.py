"""Admin page and its API: settings, usage and cost, testers, and the question log."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app import access, config, storage

router = APIRouter(include_in_schema=False)
_PAGE = Path(__file__).parent / "static" / "admin.html"


def _require_admin(request: Request) -> None:
    if not request.state.admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _tester(owner: str | None) -> str:
    return f"Tester {owner[:6]}" if owner else "Local"


def _cost(rows: list[dict]) -> float:
    return round(sum(config.cost(r["model"], r["inp"], r["out"], r["cr"], r["cw"]) or 0 for r in rows), 4)


@router.get("/me")
def me(request: Request) -> dict:
    return {"admin": bool(request.state.admin), "gated": access.enabled()}


@router.get("/admin")
def admin_page(request: Request):
    if not request.state.admin:
        return HTMLResponse(access.login_page(admin=True))
    return FileResponse(_PAGE, media_type="text/html")


@router.get("/admin/api/overview")
def overview(request: Request) -> dict:
    _require_admin(request)
    today, ever = storage.token_totals(today_only=True), storage.token_totals(today_only=False)
    testers = storage.tester_summary()
    return {
        "settings": config.all_settings(),
        "models": config.MODELS,
        "gated": access.enabled(),
        "today": {"paid_questions": sum(r["n"] for r in today), "cost": _cost(today)},
        "all_time": {"paid_questions": sum(r["n"] for r in ever), "cost": _cost(ever)},
        "charts": sum(t["charts"] for t in testers),
        "testers": [{**t, "label": _tester(t["owner"]), "owner": None} for t in testers],
    }


@router.put("/admin/api/settings")
async def save_settings(request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    try:
        return config.update(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/admin/api/queries")
def queries(request: Request, limit: int = 50, before_id: int | None = None) -> list[dict]:
    _require_admin(request)
    rows = storage.recent_queries(max(1, min(limit, 200)), before_id)
    for r in rows:
        r["tester"] = _tester(r.pop("owner"))
        r["model_label"] = config.label(r["model"])
        r["cost"] = config.cost(r["model"], r["input_tokens"], r["output_tokens"], r["cache_read_tokens"],
                                r["cache_write_tokens"]) if r["kind"] == "llm" else 0.0
    return rows


@router.put("/admin/api/queries/{query_id}/remarks")
async def save_remarks(request: Request, query_id: int) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    remarks = body.get("remarks", "").strip()
    if not storage.update_remarks(query_id, remarks or None):
        raise HTTPException(status_code=404, detail="Query not found")
    return {"ok": True}
