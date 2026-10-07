"""Admin page and its API: settings, usage and cost, testers, and the question log."""
from __future__ import annotations

import re
import secrets
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app import access, config, storage

router = APIRouter(include_in_schema=False)
_PAGE = Path(__file__).parent / "static" / "admin.html"


def _require_admin(request: Request) -> None:
    if not request.state.admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _tester(owner: str | None, labels: dict[str, str] | None = None) -> str:
    if not owner:
        return "Local"
    label = (labels or {}).get(owner)
    return f"{label} · {owner[:6]}" if label else f"Tester {owner[:6]}"


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
    testers, labels = storage.tester_summary(), storage.owner_code_labels()
    return {
        "settings": config.all_settings(),
        "models": config.MODELS,
        "gated": access.enabled(),
        "today": {"paid_questions": sum(r["n"] for r in today), "cost": _cost(today)},
        "all_time": {"paid_questions": sum(r["n"] for r in ever), "cost": _cost(ever)},
        "charts": sum(t["charts"] for t in testers),
        "testers": [{**t, "label": _tester(t["owner"], labels), "owner": None} for t in testers],
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
    labels = storage.owner_code_labels()
    for r in rows:
        r["tester"] = _tester(r.pop("owner"), labels)
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


# ----- tester access codes -----
_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes (0/o, 1/l/i)


def _new_code() -> str:
    return "sj-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def _label(body: dict) -> str:
    label = body.get("label", "")
    if not isinstance(label, str) or len(label.strip()) > 60:
        raise HTTPException(status_code=422, detail="Label must be text of 60 characters or fewer")
    return label.strip()


@router.get("/admin/api/codes")
def list_codes(request: Request) -> dict:
    _require_admin(request)
    return {"gated": access.enabled(), "codes": storage.list_codes(),
            "env_codes": len(access._codes())}


@router.post("/admin/api/codes", status_code=201)
async def create_code(request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    label, code = _label(body), (body.get("code") or "").strip()
    if code:
        if not _CODE_RE.match(code):
            raise HTTPException(status_code=422, detail="Codes need 6–40 letters, numbers, - or _")
        if access.check_code(code):
            raise HTTPException(status_code=409, detail="That code is already in use")
    else:
        code = _new_code()
    try:
        return storage.add_code(code, label)
    except sqlite3.IntegrityError as exc:  # a paused code with the same text
        raise HTTPException(status_code=409, detail="That code is already in use") from exc


@router.patch("/admin/api/codes/{code_id}")
async def edit_code(code_id: int, request: Request) -> dict:
    _require_admin(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object")
    active = body.get("active")
    if active is not None and not isinstance(active, bool):
        raise HTTPException(status_code=422, detail="active must be true or false")
    label = _label(body) if "label" in body else None
    if not storage.update_code(code_id, active=active, label=label):
        raise HTTPException(status_code=404, detail="Code not found")
    return {"ok": True}


@router.delete("/admin/api/codes/{code_id}")
def remove_code(code_id: int, request: Request) -> dict:
    _require_admin(request)
    if not storage.delete_code(code_id):
        raise HTTPException(status_code=404, detail="Code not found")
    return {"ok": True}
